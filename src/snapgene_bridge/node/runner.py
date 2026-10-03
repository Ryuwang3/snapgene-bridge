"""Use SnapGene's official ``--convert`` command as a batch oracle.

Each job is written as SnapGene-flavoured GenBank (template, features and
primers without binding sites).  One SnapGene process converts the whole
batch to ``.dna``; while importing, SnapGene computes every primer binding
site and melting temperature with its own algorithm.  The results are read
back from the ``.dna`` files.

Facts this module relies on (SnapGene 8.0.0, verified):

* ``.dna`` to ``.dna`` conversion is a byte copy, so input must be GenBank.
* Location hints on ``primer_bind`` features do not change the result.
* Primers with no site at or above the hybridization threshold (minimum Tm
  40 C by default) are silently not imported.
* The command line cannot run while the SnapGene GUI is open, and it blocks
  on any modal dialog (for example the first-run name/e-mail prompt).
"""

from __future__ import annotations

import base64
import contextlib
import fcntl
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .. import __version__
from ..errors import (
    DependencyMissingError,
    InputError,
    NodeError,
    SnapGeneBusyError,
    SnapGeneTimeoutError,
)
from ..models import IUPAC_DNA
from ..snapgene_genbank import write_snapgene_genbank
from .backends import Backend, detect_backend

LOCK_PATH = Path(tempfile.gettempdir()) / "snapgene-bridge-node.lock"
_LABEL = re.compile(r"[^A-Za-z0-9_.\-]+")


@contextlib.contextmanager
def _node_lock() -> Iterator[None]:
    """Serialize SnapGene runs: only one CLI instance can work at a time."""

    with LOCK_PATH.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _sgffp():
    try:
        import sgffp
    except ImportError as error:  # pragma: no cover - deployment problem
        raise DependencyMissingError(
            "The node needs sgffp to read SnapGene output.",
            hint="Re-run: snapgene-bridge deploy",
        ) from error
    return sgffp


def _labels(primers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Give each distinct sequence one SnapGene-safe unique label.

    SnapGene keeps one primer per sequence, so duplicates are sent once and
    their result is copied to every requested name.
    """

    to_send: list[dict[str, Any]] = []
    owners: dict[str, list[str]] = {}
    by_sequence: dict[str, str] = {}
    used: set[str] = set()
    for primer in primers:
        name = str(primer.get("name") or "primer")
        sequence = "".join(str(primer.get("sequence", "")).split()).upper()
        if not sequence or set(sequence) - IUPAC_DNA:
            raise InputError(f"Primer {name!r} has an empty or non-IUPAC sequence.")
        if sequence in by_sequence:
            owners[by_sequence[sequence]].append(name)
            continue
        base = _LABEL.sub("_", name).strip("_")[:50] or "primer"
        label, counter = base, 2
        while label in used:
            label, counter = f"{base}_{counter}", counter + 1
        used.add(label)
        by_sequence[sequence] = label
        owners[label] = [name]
        to_send.append({"name": label, "sequence": sequence, "hint": primer.get("hint")})
    return to_send, owners


def _components(raw: Any) -> list[dict[str, Any]]:
    """Normalise SnapGene's per-site alignment segments.

    ``hybridized`` is a zero-based half-open template interval; segments
    without it are primer bases that do not pair (5' tails, mismatches).
    """

    items = raw if isinstance(raw, list) else ([raw] if raw else [])
    out = []
    for item in items:
        entry: dict[str, Any] = {"bases": item.get("bases", "")}
        if "hybridizedRange" in item:
            first, last = (int(x) for x in str(item["hybridizedRange"]).split("-", 1))
            entry["hybridized"] = [first, last + 1]
        out.append(entry)
    return out


def parse_dna_result(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Map SnapGene primer label -> detailed binding sites from a ``.dna`` file."""

    reader = _sgffp().SgffReader.from_file(path)
    sites: dict[str, list[dict[str, Any]]] = {}
    if not reader.has_primers:
        return sites
    for primer in reader.primers:
        sites[primer.name] = [
            {
                "start": site.start,
                "end": site.end,
                "strand": site.bound_strand,
                "tm": site.melting_temperature,
                "annealed": site.annealed_bases,
                "components": _components(site.extras.get("Component")),
            }
            for site in primer.binding_sites
            if not site.simplified
        ]
    return sites


def _run_snapgene(backend: Backend, run_dir: Path, timeout: float) -> float:
    command = [
        backend.exe,
        "--convert",
        "SnapGene DNA",
        "--input-list",
        backend.native_path(run_dir / "inputs.txt"),
        "--output-list",
        backend.native_path(run_dir / "outputs.txt"),
    ]
    before = backend.running_pids()
    started = time.monotonic()
    try:
        subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            cwd=str(run_dir),
        )
    except subprocess.TimeoutExpired as error:
        # only processes that appeared during this run; evaluate() refuses to start otherwise
        stray = backend.running_pids() - before
        dialogs = backend.dialog_text(stray, run_dir)
        for pid in stray:
            backend.kill(pid)
        raise SnapGeneTimeoutError(
            f"SnapGene did not finish within {timeout:.0f} s and was stopped.",
            hint=(
                "A hidden dialog is usually the cause (first-run name/e-mail prompt, licence or "
                "update notice). Open SnapGene once on the node, finish the dialog, close it, "
                "and retry."
            ),
            details={"dialog_text": dialogs, "killed_pids": sorted(stray)},
        ) from error
    return time.monotonic() - started


def evaluate(request: dict[str, Any]) -> dict[str, Any]:
    jobs = request.get("jobs") or []
    if not jobs:
        raise InputError("The request contains no jobs.")
    settings = request.get("node") or {}
    backend = detect_backend(settings.get("snapgene_exe"))
    timeout = float(request.get("timeout_s") or settings.get("timeout_s") or 300)
    keep = bool(request.get("keep_files"))
    with _node_lock():
        busy = backend.running_pids()
        if busy:
            raise SnapGeneBusyError(
                "SnapGene is open on the node; its command line cannot run alongside it.",
                hint="Close every SnapGene window on the node, then retry.",
                details={"pids": sorted(busy)},
            )
        scratch = Path(settings.get("scratch_dir") or backend.default_scratch()) / "runs"
        run_dir = scratch / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        run_dir.mkdir(parents=True)
        try:
            plans = []
            for index, job in enumerate(jobs):
                sequence = "".join(str(job.get("sequence", "")).split()).upper()
                if not sequence or set(sequence) - IUPAC_DNA:
                    raise InputError(f"Job {index} has an empty or non-IUPAC template sequence.")
                to_send, owners = _labels(list(job.get("primers") or []))
                stem = f"job{index:04d}"
                (run_dir / f"{stem}.gb").write_text(
                    write_snapgene_genbank(
                        name=str(job.get("name") or stem),
                        sequence=sequence,
                        topology=str(job.get("topology") or "linear"),
                        features=job.get("features") or [],
                        primers=to_send,
                    )
                )
                plans.append((stem, to_send, owners))
            newline = backend.list_line_ending()
            for list_name, suffix in (("inputs.txt", ".gb"), ("outputs.txt", ".dna")):
                lines = [backend.native_path(run_dir / f"{stem}{suffix}") for stem, _, _ in plans]
                (run_dir / list_name).write_text(newline.join(lines) + newline)
            elapsed = _run_snapgene(backend, run_dir, timeout)
            results = []
            for (stem, to_send, owners), job in zip(plans, jobs, strict=True):
                dna = run_dir / f"{stem}.dna"
                if not dna.exists():
                    raise NodeError(
                        f"SnapGene produced no output for job {job.get('name') or stem}.",
                        hint="Check the template; rerun with keep_files to inspect the inputs.",
                    )
                sites = parse_dna_result(dna)
                primers_out = []
                for sent in to_send:
                    found = sites.get(sent["name"])
                    for owner in owners[sent["name"]]:
                        primers_out.append(
                            {
                                "name": owner,
                                "sequence": sent["sequence"],
                                "imported": found is not None,
                                "sites": found or [],
                            }
                        )
                result: dict[str, Any] = {"name": job.get("name") or stem, "primers": primers_out}
                if job.get("return_dna"):
                    result["dna_base64"] = base64.b64encode(dna.read_bytes()).decode("ascii")
                results.append(result)
        finally:
            if not keep:
                shutil.rmtree(run_dir, ignore_errors=True)
    return {
        "ok": True,
        "node_version": __version__,
        "elapsed_s": round(elapsed, 2),
        "snapgene": {"backend": backend.name, "exe": backend.exe, "version": backend.version()},
        "run_dir": str(run_dir) if keep else None,
        "jobs": results,
    }


def status(request: dict[str, Any]) -> dict[str, Any]:
    settings = request.get("node") or {}
    info: dict[str, Any] = {
        "ok": True,
        "node_version": __version__,
        "python": sys.version.split()[0],
    }
    try:
        from importlib.metadata import version as package_version

        import sgffp  # noqa: F401

        info["sgffp"] = package_version("sgffp")
    except Exception:  # pragma: no cover - deployment problem
        info["sgffp"] = None
    try:
        backend = detect_backend(settings.get("snapgene_exe"))
    except NodeError as error:
        info.update(snapgene_found=False, problem=error.as_dict())
        return info
    scratch = Path(settings.get("scratch_dir") or backend.default_scratch())
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        probe = scratch / ".write-test"
        probe.write_text("ok")
        probe.unlink()
        writable = True
    except OSError:
        writable = False
    info.update(
        snapgene_found=True,
        backend=backend.name,
        backend_verified=backend.verified,
        snapgene_exe=backend.exe,
        snapgene_version=backend.version(),
        snapgene_running_pids=sorted(backend.running_pids()),
        scratch_dir=str(scratch),
        scratch_writable=writable,
    )
    return info
