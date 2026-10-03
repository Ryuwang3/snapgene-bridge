"""Command-line interface with a stable JSON envelope for coding agents."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .config import MODES, NodeConfig, load_config, save_config
from .design import DesignConfig, design_clone, design_pcr
from .design.common import order_sheet, pair_order_rows
from .errors import BridgeError, InputError
from .io import read_record, write_record
from .models import MoleculeRecord, Primer, normalize_sequence
from .oracle import EstimateOracle, SnapGeneOracle
from .seqtools import format_location, parse_location

SCHEMA_VERSION = "2"


# ---------------------------------------------------------------- arguments


def _length_range(text: str) -> tuple[int, int]:
    try:
        low, high = (int(part) for part in text.replace("..", "-").split("-", 1))
    except ValueError as error:
        raise argparse.ArgumentTypeError("use MIN-MAX, for example 18-28") from error
    if not 0 < low <= high:
        raise argparse.ArgumentTypeError("MIN must be positive and not larger than MAX")
    return low, high


def _design_options(parser: argparse.ArgumentParser, lengths: str) -> None:
    parser.add_argument("input", type=Path, help="Template: .dna, .gb/.gbk, or .fasta")
    parser.add_argument("--feature", help="Use the span (and strand) of this annotated feature.")
    parser.add_argument("--target-tm", type=float, default=60.0, help="Target SnapGene Tm in C.")
    parser.add_argument("--max-dtm", type=float, default=2.0, help="Max Tm difference in a pair.")
    parser.add_argument(
        "--length",
        type=_length_range,
        default=_length_range(lengths),
        help=f"Annealing length range, default {lengths}.",
    )
    parser.add_argument(
        "--offtarget-max-tm",
        type=float,
        default=45.0,
        help="Reject candidates with another site at or above this SnapGene Tm.",
    )
    parser.add_argument("--alternatives", type=int, default=5, help="Pairs to report.")
    parser.add_argument("--name", help="Primer name prefix (default: feature or molecule name).")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the template plus chosen primers (.dna from SnapGene, or .gb).",
    )
    parser.add_argument("--order", type=Path, help="Write a tab-separated oligo order sheet.")
    parser.add_argument("--force", action="store_true", help="Allow replacing --output/--order.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use local estimates instead of SnapGene (values are not SnapGene's).",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="snapgene-bridge",
        description="Agent-native primer design that asks a local SnapGene install for Tm and "
        "binding sites. Every command prints one JSON object.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Write the client config (where the SnapGene node is).")
    init.add_argument("--host", help="SSH alias or user@host of the SnapGene node.")
    init.add_argument("--mode", choices=MODES, help="ssh (default with --host), local, or off.")
    init.add_argument(
        "--dir", help="Install directory on the node (default ~/snapgene-bridge-node)."
    )
    init.add_argument(
        "--snapgene-exe", help="SnapGene executable path on the node, if not standard."
    )
    init.add_argument("--scratch-dir", help="Scratch directory on the node, if not the default.")
    init.add_argument("--timeout", type=int, help="Seconds allowed per SnapGene run (default 300).")

    status = sub.add_parser("status", help="Report local capabilities and SnapGene node health.")
    status.add_argument("--no-node", action="store_true", help="Skip contacting the node.")

    sub.add_parser("deploy", help="Install or update snapgene-bridge on the SnapGene node.")

    selftest = sub.add_parser("selftest", help="Compare the node against stored SnapGene results.")
    selftest.add_argument("--quick", action="store_true", help="Use 40 of the 200 random primers.")

    read = sub.add_parser("read", help="Read one molecule and emit normalized JSON.")
    read.add_argument("input", type=Path)
    validate = sub.add_parser("validate", help="Parse and validate one molecule.")
    validate.add_argument("input", type=Path)

    check = sub.add_parser("check", help="SnapGene binding sites and Tm for given primers.")
    check.add_argument("input", type=Path, help="Template: .dna, .gb/.gbk, or .fasta")
    check.add_argument(
        "--primer",
        action="append",
        default=[],
        metavar="NAME=SEQUENCE",
        help="Primer to check (repeatable).",
    )
    check.add_argument("--primers", type=Path, help="FASTA or NAME<tab>SEQUENCE file of primers.")
    check.add_argument(
        "--offline", action="store_true", help="Local estimates instead of SnapGene."
    )
    check.add_argument("--output", type=Path, help="Write template plus these primers.")
    check.add_argument("--force", action="store_true")

    pcr = sub.add_parser("pcr", help="Design a PCR pair whose product contains a target region.")
    _design_options(pcr, "18-28")
    pcr.add_argument("--target", help="Region to amplify, 1-based inclusive, e.g. 1627..2486.")
    pcr.add_argument(
        "--product-size",
        type=_length_range,
        help="Allowed product length MIN-MAX (default: target + 56 .. target + 800).",
    )
    pcr.add_argument("--candidates", type=int, default=40, help="primer3 pairs to propose.")

    clone = sub.add_parser("clone", help="Design cloning primers fixed at the insert ends.")
    _design_options(clone, "16-36")
    clone.add_argument("--region", help="Insert, 1-based inclusive, e.g. 1627..2486.")
    clone.add_argument(
        "--strand", choices=("+", "-"), help="Insert orientation (default: feature strand, else +)."
    )
    clone.add_argument("--tail-f", default="", help="5' tail added to the forward primer.")
    clone.add_argument("--tail-r", default="", help="5' tail added to the reverse primer.")

    open_parser = sub.add_parser("open", help="Open a file in a local desktop application.")
    open_parser.add_argument("input", type=Path)
    open_parser.add_argument("--app", default="SnapGene", help="macOS application name.")
    open_parser.add_argument("--dry-run", action="store_true", help="Only print the command.")
    return parser


# ---------------------------------------------------------------- helpers


def _envelope(command: str, **payload: Any) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "ok": True, "command": command, **payload}


def _oracle(cfg: NodeConfig, offline: bool):
    return EstimateOracle() if offline else SnapGeneOracle(cfg)


def _region(record: MoleculeRecord, location: str | None, feature: str | None, flag: str):
    """Resolve ``--target/--region`` or ``--feature`` to (start, end, strand, label)."""

    if bool(location) == bool(feature):
        raise InputError(f"Give exactly one of {flag} or --feature.")
    if location:
        start, end = parse_location(location, record.length)
        if end <= start and record.topology != "circular":
            raise InputError(f"{location} runs backwards on a linear molecule.")
        return start, end, None, None
    matches = [f for f in record.features if f.name.lower() == feature.lower()]
    if not matches:
        names = sorted({f.name for f in record.features})
        raise InputError(
            f"No feature named {feature!r}.",
            hint="Available features: " + (", ".join(names[:40]) or "none"),
        )
    if len(matches) > 1:
        raise InputError(f"Feature name {feature!r} is ambiguous ({len(matches)} matches).")
    found = matches[0]
    segments = sorted(found.segments, key=lambda s: s.start)
    n = record.length
    starts_at_zero = [s for s in segments if s.start == 0]
    ends_at_n = [s for s in segments if s.end == n]
    if record.topology == "circular" and starts_at_zero and ends_at_n and len(segments) > 1:
        start, end = ends_at_n[-1].start, starts_at_zero[0].end  # origin-spanning feature
    else:
        start, end = segments[0].start, segments[-1].end
    strand = found.strand if found.strand in ("+", "-") else None
    return start, end, strand, found.name


def _write_bytes(path: Path, data: bytes | str, force: bool) -> str:
    target = path.expanduser()
    if target.exists() and not force:
        raise InputError(
            f"Refusing to overwrite existing output: {target}",
            hint="Choose a new output path or pass --force explicitly.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        target.write_bytes(data)
    else:
        target.write_text(data)
    return str(target)


def _write_molecule(
    cfg: NodeConfig,
    record: MoleculeRecord,
    new_primers: list[dict[str, str]],
    path: Path,
    force: bool,
    offline: bool,
) -> dict[str, Any]:
    """Write template + existing primers + new primers.

    For ``.dna`` with a node, the file is produced by SnapGene itself, so its
    binding sites and Tm are SnapGene's.  ``.gb`` is written locally in the
    GenBank-SnapGene flavour (SnapGene computes the sites when it opens it).
    """

    existing = {p.name for p in record.primers}
    merged = list(record.primers) + [
        Primer(name=p["name"], sequence=p["sequence"])
        for p in new_primers
        if p["name"] not in existing
    ]
    updated = record.with_primers(merged)
    if path.suffix.lower() == ".dna" and not offline:
        run = SnapGeneOracle(cfg).evaluate(
            updated,
            [{"name": p.name, "sequence": p.sequence} for p in merged],
            return_dna=True,
            include_features=True,
        )
        written = _write_bytes(path, run.dna or b"", force)
        return {
            "path": written,
            "format": "snapgene (generated by SnapGene)",
            "warnings": ["Feature colours, notes and history from the input are not carried over."]
            if record.features
            else [],
        }
    report = write_record(updated, path, force=force)
    return {"path": report.path, "format": report.format, "warnings": list(report.warnings)}


def _primers_from_args(values: list[str], file: Path | None) -> list[dict[str, str]]:
    primers: list[dict[str, str]] = []
    for value in values:
        name, sep, sequence = value.partition("=")
        if not sep:
            raise InputError(f"--primer expects NAME=SEQUENCE, got {value!r}.")
        primers.append({"name": name.strip(), "sequence": normalize_sequence(sequence)})
    if file:
        text = file.expanduser().read_text()
        if text.lstrip().startswith(">"):
            name, chunks = None, []
            for line in text.splitlines() + [">"]:
                if line.startswith(">"):
                    if name:
                        primers.append(
                            {"name": name, "sequence": normalize_sequence("".join(chunks))}
                        )
                    name, chunks = line[1:].strip().split(" ")[0] or None, []
                elif line.strip():
                    chunks.append(line.strip())
        else:
            for line in text.splitlines():
                parts = [p for p in line.replace(",", "\t").split("\t") if p.strip()]
                if len(parts) < 2:
                    parts = line.split()
                if len(parts) >= 2:
                    try:
                        primers.append(
                            {"name": parts[0].strip(), "sequence": normalize_sequence(parts[1])}
                        )
                    except BridgeError:
                        continue  # header or comment line
    if not primers:
        raise InputError("No primers given.", hint="Use --primer NAME=SEQUENCE or --primers FILE.")
    names = [p["name"] for p in primers]
    if len(set(names)) != len(names):
        raise InputError("Primer names must be unique.")
    return primers


# ---------------------------------------------------------------- commands


def _status(cfg: NodeConfig, skip_node: bool) -> dict[str, Any]:
    local = {
        "sgffp": importlib.util.find_spec("sgffp") is not None,
        "biopython": importlib.util.find_spec("Bio") is not None,
        "primer3_py": importlib.util.find_spec("primer3") is not None,
    }
    node: dict[str, Any] = {"contacted": False}
    ready = False
    if cfg.mode != "off" and not skip_node:
        try:
            info = SnapGeneOracle(cfg).status()
            node = {"contacted": True, **info}
            problems = []
            if not info.get("snapgene_found"):
                problems.append("SnapGene not found on the node")
            if info.get("snapgene_running_pids"):
                problems.append("SnapGene is open on the node; close it before running commands")
            if info.get("scratch_writable") is False:
                problems.append("node scratch directory is not writable")
            if info.get("node_version") != __version__:
                problems.append(
                    f"node runs {info.get('node_version')}, client is {__version__}: run deploy"
                )
            node["problems"] = problems
            ready = not problems
        except BridgeError as error:
            node = {"contacted": False, "error": error.as_dict()}
    return _envelope(
        "status",
        version=__version__,
        platform={"system": platform.system(), "python": platform.python_version()},
        local_dependencies=local,
        config=cfg.to_dict(),
        node=node,
        ready=ready,
    )


def _check(args: argparse.Namespace, cfg: NodeConfig) -> dict[str, Any]:
    record = read_record(args.input)
    primers = _primers_from_args(args.primer, args.primers)
    run = _oracle(cfg, args.offline).evaluate(record, primers)
    n = record.length
    results = []
    for primer in primers:
        verdict = run.verdicts[primer["name"]]
        results.append(
            {
                "name": primer["name"],
                "sequence": primer["sequence"],
                "length": len(primer["sequence"]),
                "imported": verdict.imported,
                "sites": [site.to_dict(n) for site in verdict.sites],
                "note": None
                if verdict.imported
                else "No binding site at or above SnapGene's hybridization threshold (Tm 40 C).",
            }
        )
    payload: dict[str, Any] = {
        "input": str(args.input),
        "molecule": {"name": record.name, "length": n, "topology": record.topology},
        "tm_standard": run.tm_standard,
        "oracle": run.meta(),
        "primers": results,
    }
    if args.output:
        payload["output"] = _write_molecule(
            cfg, record, primers, args.output, args.force, args.offline
        )
    return _envelope("check", **payload)


def _design_config(args: argparse.Namespace) -> DesignConfig:
    return DesignConfig(
        target_tm=args.target_tm,
        max_tm_difference=args.max_dtm,
        min_length=args.length[0],
        max_length=args.length[1],
        offtarget_max_tm=args.offtarget_max_tm,
        alternatives=max(1, args.alternatives),
    )


def _design(args: argparse.Namespace, cfg: NodeConfig) -> dict[str, Any]:
    record = read_record(args.input)
    oracle = _oracle(cfg, args.offline)
    config = _design_config(args)
    if args.command == "pcr":
        start, end, _, label = _region(record, args.target, args.feature, "--target")
        prefix = args.name or label or record.name
        low, high = args.product_size or (None, None)
        result = design_pcr(
            record,
            start,
            end,
            oracle=oracle,
            config=config,
            product_min=low,
            product_max=high,
            candidate_pairs=args.candidates,
            name_prefix=prefix,
        )
    else:
        start, end, strand, label = _region(record, args.region, args.feature, "--region")
        prefix = args.name or label or record.name
        result = design_clone(
            record,
            start,
            end,
            oracle=oracle,
            config=config,
            insert_strand=args.strand or strand or "+",
            tail_f=normalize_sequence(args.tail_f) if args.tail_f else "",
            tail_r=normalize_sequence(args.tail_r) if args.tail_r else "",
            name_prefix=prefix,
        )
    payload: dict[str, Any] = {"input": str(args.input), "design": result.to_dict()}
    best = result.best
    chosen = [{"name": c.name, "sequence": c.sequence} for c in (best.forward, best.reverse)]
    if args.output:
        payload["output"] = _write_molecule(
            cfg, record, chosen, args.output, args.force, args.offline
        )
    if args.order:
        rows = pair_order_rows(best, result.run.tm_standard)
        payload["order_sheet"] = _write_bytes(args.order, order_sheet(rows), args.force)
    if result.run.source != "snapgene":
        payload.setdefault("warnings", []).append(
            "Offline mode: Tm values are local estimates, not SnapGene's. Re-run with a node "
            "before ordering."
        )
    return _envelope(args.command, **payload)


def _open_file(path: Path, app: str, dry_run: bool) -> dict[str, Any]:
    if not path.exists():
        raise InputError(f"File does not exist: {path}")
    if sys.platform == "darwin":
        command = ["open", "-a", app, str(path)]
    elif sys.platform == "win32":
        command = ["cmd", "/c", "start", "", str(path)]
    else:
        command = ["xdg-open", str(path)]
    if not dry_run:
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise InputError(
                f"Could not open {path} with {app!r}: {error}",
                hint="SnapGene may live on the node rather than this machine; copy the file there.",
            ) from error
    return _envelope(
        "open", path=str(path), application=app, launch_command=command, dry_run=dry_run
    )


def _init(args: argparse.Namespace) -> dict[str, Any]:
    cfg = load_config()
    for key, value in (
        ("host", args.host),
        ("dir", args.dir),
        ("snapgene_exe", args.snapgene_exe),
        ("scratch_dir", args.scratch_dir),
    ):
        if value:
            setattr(cfg, key, value)
    if args.timeout:
        cfg.timeout_s = args.timeout
    cfg.mode = args.mode or ("ssh" if cfg.host else cfg.mode)
    path = save_config(cfg)
    cfg.path = str(path)
    return _envelope(
        "init",
        config=cfg.to_dict(),
        next_steps=[
            "snapgene-bridge deploy",
            "snapgene-bridge status",
            "snapgene-bridge selftest --quick",
        ],
    )


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "init":
        return _init(args)
    cfg = load_config()
    if args.command == "status":
        return _status(cfg, args.no_node)
    if args.command == "deploy":
        from .deploy import deploy

        return _envelope("deploy", **deploy(cfg))
    if args.command == "selftest":
        from .selftest import run_selftest

        report = run_selftest(SnapGeneOracle(cfg), quick=args.quick)
        return _envelope("selftest", **report)
    if args.command in ("read", "validate"):
        record = read_record(args.input)
        record.validate()
        if args.command == "read":
            return _envelope("read", input=str(args.input), record=record.to_dict())
        return _envelope(
            "validate",
            input=str(args.input),
            name=record.name,
            length=record.length,
            topology=record.topology,
            feature_count=len(record.features),
            primer_count=len(record.primers),
            features=[
                {
                    "name": f.name,
                    "type": f.type,
                    "strand": f.strand,
                    "location": format_location(f.start, f.end, record.length),
                }
                for f in record.features
            ],
        )
    if args.command == "check":
        return _check(args, cfg)
    if args.command in ("pcr", "clone"):
        return _design(args, cfg)
    if args.command == "open":
        return _open_file(args.input, args.app, args.dry_run)
    raise InputError(f"Unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = _dispatch(args)
    except BridgeError as error:
        result = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "command": args.command,
            "error": error.as_dict(),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    except Exception as error:  # keep the agent contract intact for unexpected bugs
        result = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "command": args.command,
            "error": {"code": "internal_error", "message": f"{type(error).__name__}: {error}"},
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == "selftest" and not result.get("passed", True):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
