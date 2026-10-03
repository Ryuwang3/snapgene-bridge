"""Sequence helpers shared by the client and the SnapGene node.

Intervals are zero-based and half-open.  On a circular molecule an interval
whose end is not greater than its start wraps through the origin.
"""

from __future__ import annotations

from .errors import InputError

_COMPLEMENT = str.maketrans(
    "ACGTRYKMSWBDHVNacgtrykmswbdhvn",
    "TGCAYRMKSWVHDBNtgcayrmkswvhdbn",
)


def revcomp(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


def complement(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)


def gc_fraction(sequence: str) -> float:
    if not sequence:
        return 0.0
    return sum(base in "GCgcSs" for base in sequence) / len(sequence)


def interval_length(start: int, end: int, length: int, circular: bool) -> int:
    if end > start:
        return end - start
    if circular:
        return length - start + end
    raise InputError(f"Interval [{start}, {end}) is empty or reversed on a linear molecule.")


def slice_interval(sequence: str, start: int, end: int, circular: bool) -> str:
    """Return the top-strand bases of an interval, wrapping through the origin when circular."""

    n = len(sequence)
    if not (0 <= start <= n and 0 <= end <= n):
        raise InputError(f"Interval [{start}, {end}) lies outside a {n} bp molecule.")
    if end > start:
        return sequence[start:end]
    if circular:
        return sequence[start:] + sequence[:end]
    raise InputError(f"Interval [{start}, {end}) is empty or reversed on a linear molecule.")


def window(sequence: str, start: int, end: int, circular: bool) -> str:
    """Bases from start to end; wraps when circular, drops off-end positions when linear."""

    n = len(sequence)
    out = []
    for position in range(start, end):
        if 0 <= position < n:
            out.append(sequence[position])
        elif circular:
            out.append(sequence[position % n])
    return "".join(out)


def parse_location(text: str, length: int) -> tuple[int, int]:
    """Parse a GenBank-style 1-based inclusive location such as ``1627..2486``.

    Returns a zero-based half-open interval.  ``2600..120`` on a 2686 bp
    plasmid describes an origin-spanning interval and returns ``(2599, 120)``.
    """

    cleaned = text.strip().replace(",", "")
    for separator in ("..", "-", ":"):
        if separator in cleaned:
            left, right = cleaned.split(separator, 1)
            break
    else:
        raise InputError(
            f"Cannot parse location {text!r}.",
            hint="Use 1-based inclusive GenBank style, for example 1627..2486.",
        )
    try:
        first, last = int(left), int(right)
    except ValueError as error:
        raise InputError(f"Cannot parse location {text!r}.") from error
    if not (1 <= first <= length and 1 <= last <= length):
        raise InputError(f"Location {text!r} lies outside the {length} bp molecule.")
    if first == last + 1:
        raise InputError(f"Location {text!r} would cover the whole molecule.")
    return first - 1, last


def format_location(start: int, end: int, length: int) -> str:
    """Inverse of :func:`parse_location` for display."""

    last = end if end > 0 else length
    return f"{start + 1}..{last}"
