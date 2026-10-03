"""Command-line interface with a stable JSON envelope for coding agents."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .errors import BridgeError, InputError
from .io import read_record, write_record
from .primer_design import PrimerDesignConfig, design_primers

SCHEMA_VERSION = "1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="snapgene-bridge",
        description="Agent-native, file-first SnapGene-compatible workflows.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Report installed capabilities and host information.")

    read_parser = subparsers.add_parser("read", help="Read one molecule and emit normalized JSON.")
    read_parser.add_argument("input", type=Path)

    validate_parser = subparsers.add_parser("validate", help="Parse and validate one molecule.")
    validate_parser.add_argument("input", type=Path)

    primers_parser = subparsers.add_parser(
        "primers", help="Design a PCR primer pair for a target interval."
    )
    primers_parser.add_argument("input", type=Path)
    primers_parser.add_argument(
        "--target",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        required=True,
        help="Zero-based, half-open target interval.",
    )
    primers_parser.add_argument("--output", type=Path, help="Optional new .dna/.gb/.fasta output.")
    primers_parser.add_argument("--force", action="store_true", help="Allow replacing --output.")
    primers_parser.add_argument(
        "--pair", type=int, default=0, help="Pair index to write, default 0."
    )
    primers_parser.add_argument("--num-return", type=int, default=5)
    primers_parser.add_argument("--min-tm", type=float, default=58.0)
    primers_parser.add_argument("--opt-tm", type=float, default=60.0)
    primers_parser.add_argument("--max-tm", type=float, default=62.0)
    primers_parser.add_argument("--min-product-size", type=int, default=100)
    primers_parser.add_argument("--max-product-size", type=int, default=3000)
    primers_parser.add_argument(
        "--tm-standard",
        default="primer3",
        choices=("primer3",),
        help="Thermodynamic standard recorded in the output.",
    )

    open_parser = subparsers.add_parser(
        "open", help="Open a generated file in a desktop application."
    )
    open_parser.add_argument("input", type=Path)
    open_parser.add_argument("--app", default="SnapGene", help="macOS application name.")
    open_parser.add_argument(
        "--dry-run", action="store_true", help="Only print the launch command."
    )
    return parser


def _envelope(command: str, **payload: Any) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "ok": True, "command": command, **payload}


def _dependency_status(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _status() -> dict[str, Any]:
    applications: dict[str, bool] = {}
    if sys.platform == "darwin":
        applications = {
            "SnapGene": Path("/Applications/SnapGene.app").exists(),
            "SnapGene Viewer": Path("/Applications/SnapGene Viewer.app").exists(),
        }
    else:
        applications = {"SnapGene": shutil.which("SnapGene") is not None}
    return _envelope(
        "status",
        version=__version__,
        platform={
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        dependencies={
            "sgffp": _dependency_status("sgffp"),
            "biopython": _dependency_status("Bio"),
            "primer3_py": _dependency_status("primer3"),
            "pydna": _dependency_status("pydna"),
        },
        applications=applications,
        capabilities={
            "read_fasta": True,
            "read_genbank": _dependency_status("Bio"),
            "read_snapgene": _dependency_status("sgffp"),
            "write_snapgene": _dependency_status("sgffp"),
            "design_primers": _dependency_status("primer3"),
            "in_process_snapgene_control": False,
        },
    )


def _run_primers(args: argparse.Namespace) -> dict[str, Any]:
    record = read_record(args.input)
    config = PrimerDesignConfig(
        num_return=args.num_return,
        min_tm=args.min_tm,
        opt_tm=args.opt_tm,
        max_tm=args.max_tm,
        min_product_size=args.min_product_size,
        max_product_size=args.max_product_size,
        tm_standard=args.tm_standard,
    )
    result = design_primers(record, args.target[0], args.target[1], config=config)
    payload: dict[str, Any] = {
        "input": str(args.input),
        "record": record.to_dict(),
        "design": result.to_dict(),
    }
    if args.output:
        if not 0 <= args.pair < len(result.pairs):
            raise InputError(f"Pair index {args.pair} is outside the returned range.")
        selected = result.pairs[args.pair]
        updated = record.with_primers([selected.forward, selected.reverse])
        report = write_record(updated, args.output, force=args.force)
        payload["output"] = {
            "path": report.path,
            "format": report.format,
            "warnings": list(report.warnings),
            "pair_index": args.pair,
        }
    return _envelope("primers", **payload)


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
                hint="Use --dry-run to inspect the command or open the file manually.",
            ) from error
    return _envelope(
        "open", path=str(path), application=app, launch_command=command, dry_run=dry_run
    )


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "status":
        return _status()
    if args.command == "read":
        record = read_record(args.input)
        return _envelope("read", input=str(args.input), record=record.to_dict())
    if args.command == "validate":
        record = read_record(args.input)
        record.validate()
        return _envelope(
            "validate",
            input=str(args.input),
            name=record.name,
            length=record.length,
            feature_count=len(record.features),
            primer_count=len(record.primers),
        )
    if args.command == "primers":
        return _run_primers(args)
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
            "error": {"code": "internal_error", "message": str(error)},
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
