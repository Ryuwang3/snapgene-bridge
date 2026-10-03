"""Write GenBank text in the flavor SnapGene exports ("GenBank - SnapGene").

SnapGene imports ``primer_bind`` features as real primers, and computes their
binding sites and melting temperatures itself, only when the file carries the
``JOURNAL   Exported ... from SnapGene ...`` reference line that its own
exporter writes.  Without that line the same features come in as plain
annotations.  This was verified with SnapGene 8.0.0; colour names and label
quoting did not matter.

The writer is pure Python so it can run on the SnapGene node without extra
dependencies.  Inputs are plain dictionaries matching the node protocol.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterable, Mapping
from typing import Any

QUALIFIER_INDENT = " " * 21
WRAP_WIDTH = 58
_LOCUS_NAME = re.compile(r"[^A-Za-z0-9_.\-]")
_FEATURE_KEY = re.compile(r"^[A-Za-z0-9_'\-*]{1,15}$")


def _clean_text(value: Any, limit: int = 120) -> str:
    text = re.sub(r"[\r\n\t\"]", " ", str(value)).strip()
    return text[:limit] or "unnamed"


def _qualifier(key: str, value: str, *, quote: bool = True) -> str:
    """Render one qualifier, wrapping at word boundaries like SnapGene does.

    Long unbroken tokens (sequences) are kept on one line rather than being
    split, so the importer never sees a space inside a primer sequence.
    """

    body = f'/{key}="{value}"' if quote else f"/{key}={value}"
    lines: list[str] = []
    current = ""
    for word in body.split(" "):
        candidate = f"{current} {word}" if current else word
        if current and len(candidate) > WRAP_WIDTH:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)
    return "".join(f"{QUALIFIER_INDENT}{line}\n" for line in lines)


def _split_wrapping(start: int, end: int, length: int) -> list[tuple[int, int]]:
    """Split an origin-spanning segment into two linear pieces."""

    if end > start:
        return [(start, end)]
    pieces = [(start, length)]
    if end > 0:
        pieces.append((0, end))
    return pieces


def _location(segments: Iterable[tuple[int, int]], strand: str, length: int) -> str:
    parts: list[str] = []
    for start, end in segments:
        for piece_start, piece_end in _split_wrapping(start, end, length):
            parts.append(
                f"{piece_start + 1}"
                if piece_end - piece_start == 1
                else f"{piece_start + 1}..{piece_end}"
            )
    location = parts[0] if len(parts) == 1 else f"join({','.join(parts)})"
    return f"complement({location})" if strand == "-" else location


def _feature_key(value: str) -> str:
    key = str(value or "misc_feature").strip().replace(" ", "_")
    return key if _FEATURE_KEY.match(key) else "misc_feature"


def primer_hint(primer: Mapping[str, Any], length: int) -> tuple[list[tuple[int, int]], str]:
    """Location written for a primer.

    SnapGene recomputes every binding site on import, so the hint only has to
    be a valid location.  A known site is used when the caller supplies one.
    """

    hint = primer.get("hint")
    if hint and 0 <= int(hint["start"]) < length and 0 < int(hint["end"]) <= length:
        return [(int(hint["start"]), int(hint["end"]))], str(hint.get("strand", "+"))
    span = max(1, min(len(primer["sequence"]), length))
    return [(0, span)], "+"


def write_snapgene_genbank(
    *,
    name: str,
    sequence: str,
    topology: str = "linear",
    features: Iterable[Mapping[str, Any]] = (),
    primers: Iterable[Mapping[str, Any]] = (),
    snapgene_version: str = "8.0.0",
    today: _dt.date | None = None,
) -> str:
    """Return GenBank text that SnapGene imports with primers.

    ``features`` items: ``name``, ``type``, ``strand`` and ``segments`` (each a
    zero-based half-open ``start``/``end`` mapping).  ``primers`` items:
    ``name``, ``sequence`` and an optional ``hint`` site.
    """

    sequence = sequence.upper()
    length = len(sequence)
    if length == 0:
        raise ValueError("Cannot write an empty sequence.")
    today = today or _dt.date.today()
    locus = (_LOCUS_NAME.sub("_", name) or "sequence")[:16]
    shape = "circular" if topology == "circular" else "linear  "
    out = [
        f"LOCUS       {locus:<16} {length:>11} bp    DNA     {shape} SYN "
        f"{today.strftime('%d-%b-%Y').upper()}\n",
        f"DEFINITION  {_clean_text(name, 60)}.\n",
        "ACCESSION   .\n",
        "VERSION     .\n",
        "KEYWORDS    .\n",
        "SOURCE      synthetic DNA construct\n",
        "  ORGANISM  synthetic DNA construct\n",
        f"REFERENCE   1  (bases 1 to {length})\n",
        "  AUTHORS   snapgene-bridge\n",
        "  TITLE     Direct Submission\n",
        f"  JOURNAL   Exported {today.strftime('%b')} {today.day}, {today.year} "
        f"from SnapGene {snapgene_version}\n",
        "            https://www.snapgene.com\n",
        "FEATURES             Location/Qualifiers\n",
        f"     source          1..{length}\n",
        _qualifier("mol_type", "other DNA"),
        _qualifier("organism", "synthetic DNA construct"),
    ]
    for feature in features:
        segments = [(int(s["start"]), int(s["end"])) for s in feature.get("segments", [])]
        if not segments:
            continue
        out.append(
            f"     {_feature_key(feature.get('type')):<16}"
            f"{_location(segments, str(feature.get('strand', '+')), length)}\n"
        )
        out.append(_qualifier("label", _clean_text(feature.get("name", "feature")), quote=False))
    for primer in primers:
        segments, strand = primer_hint(primer, length)
        out.append(f"     primer_bind     {_location(segments, strand, length)}\n")
        out.append(_qualifier("label", _clean_text(primer["name"], 60), quote=False))
        out.append(_qualifier("note", f"color: black; sequence: {primer['sequence'].upper()}"))
    out.append("ORIGIN\n")
    lower = sequence.lower()
    for offset in range(0, length, 60):
        chunk = " ".join(lower[i : i + 10] for i in range(offset, min(offset + 60, length), 10))
        out.append(f"{offset + 1:>9} {chunk}\n")
    out.append("//\n")
    return "".join(out)
