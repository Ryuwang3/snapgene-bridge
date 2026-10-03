"""Small, format-neutral models used at the bridge boundary.

Coordinates are always zero-based and half-open.  Keeping that contract in
one place prevents format adapters from leaking SnapGene's mixed coordinate
conventions into agent-facing JSON.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .errors import ValidationError

IUPAC_DNA = frozenset("ACGTRYSWKMBDHVN")
TOPOLOGIES = frozenset({"linear", "circular"})
STRANDS = frozenset({"+", "-", "."})


def normalize_sequence(value: str) -> str:
    """Return an uppercase, whitespace-free IUPAC DNA sequence."""

    sequence = "".join(value.split()).upper()
    invalid = sorted(set(sequence) - IUPAC_DNA)
    if invalid:
        raise ValidationError(
            f"Sequence contains unsupported symbols: {', '.join(invalid)}",
            hint="Use IUPAC DNA symbols and remove alignment gaps before importing.",
        )
    return sequence


@dataclass(frozen=True)
class Segment:
    """A zero-based half-open interval on a molecule."""

    start: int
    end: int

    def validate(self, sequence_length: int) -> None:
        if self.start < 0 or self.end < 0 or self.start >= self.end:
            raise ValidationError(f"Invalid segment [{self.start}, {self.end}).")
        if self.end > sequence_length:
            raise ValidationError(
                f"Segment [{self.start}, {self.end}) exceeds sequence length {sequence_length}."
            )

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Segment:
        return cls(start=int(value["start"]), end=int(value["end"]))


@dataclass(frozen=True)
class Feature:
    """An annotated sequence feature, possibly made of joined segments."""

    name: str
    type: str
    segments: tuple[Segment, ...]
    strand: str = "."
    qualifiers: dict[str, Any] = field(default_factory=dict)

    @property
    def start(self) -> int:
        return min(segment.start for segment in self.segments)

    @property
    def end(self) -> int:
        return max(segment.end for segment in self.segments)

    def validate(self, sequence_length: int) -> None:
        if not self.name:
            raise ValidationError("Feature name cannot be empty.")
        if not self.type:
            raise ValidationError(f"Feature {self.name!r} has no type.")
        if self.strand not in STRANDS:
            raise ValidationError(f"Feature {self.name!r} has invalid strand {self.strand!r}.")
        if not self.segments:
            raise ValidationError(f"Feature {self.name!r} has no segments.")
        for segment in self.segments:
            segment.validate(sequence_length)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "segments": [segment.to_dict() for segment in self.segments],
            "strand": self.strand,
            "qualifiers": self.qualifiers,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Feature:
        segments = tuple(Segment.from_dict(item) for item in value["segments"])
        return cls(
            name=str(value["name"]),
            type=str(value["type"]),
            segments=segments,
            strand=str(value.get("strand", ".")),
            qualifiers=dict(value.get("qualifiers", {})),
        )


@dataclass(frozen=True)
class Primer:
    """A primer and, when known, its annealed binding interval."""

    name: str
    sequence: str
    strand: str = "+"
    binding_start: int | None = None
    binding_end: int | None = None
    tm_celsius: float | None = None
    tm_standard: str = "primer3"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sequence", normalize_sequence(self.sequence))

    def validate(self, sequence_length: int) -> None:
        if not self.name:
            raise ValidationError("Primer name cannot be empty.")
        if not self.sequence:
            raise ValidationError(f"Primer {self.name!r} has an empty sequence.")
        if self.strand not in {"+", "-"}:
            raise ValidationError(f"Primer {self.name!r} has invalid strand {self.strand!r}.")
        if (self.binding_start is None) != (self.binding_end is None):
            raise ValidationError(
                f"Primer {self.name!r} must provide both binding_start and binding_end."
            )
        if self.binding_start is not None and self.binding_end is not None:
            Segment(self.binding_start, self.binding_end).validate(sequence_length)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sequence": self.sequence,
            "strand": self.strand,
            "binding_start": self.binding_start,
            "binding_end": self.binding_end,
            "tm_celsius": self.tm_celsius,
            "tm_standard": self.tm_standard,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Primer:
        return cls(
            name=str(value["name"]),
            sequence=str(value["sequence"]),
            strand=str(value.get("strand", "+")),
            binding_start=(
                int(value["binding_start"]) if value.get("binding_start") is not None else None
            ),
            binding_end=(
                int(value["binding_end"]) if value.get("binding_end") is not None else None
            ),
            tm_celsius=(
                float(value["tm_celsius"]) if value.get("tm_celsius") is not None else None
            ),
            tm_standard=str(value.get("tm_standard", "primer3")),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass
class MoleculeRecord:
    """The stable record exchanged between adapters and operations."""

    name: str
    sequence: str
    topology: str = "linear"
    features: list[Feature] = field(default_factory=list)
    primers: list[Primer] = field(default_factory=list)
    source_format: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.sequence = normalize_sequence(self.sequence)

    @property
    def length(self) -> int:
        return len(self.sequence)

    def validate(self) -> None:
        if not self.name:
            raise ValidationError("Molecule name cannot be empty.")
        if self.topology not in TOPOLOGIES:
            raise ValidationError(f"Unsupported topology {self.topology!r}.")
        if not self.sequence:
            raise ValidationError("Molecule sequence cannot be empty.")
        for feature in self.features:
            feature.validate(self.length)
        for primer in self.primers:
            primer.validate(self.length)

    def with_primers(self, primers: Iterable[Primer]) -> MoleculeRecord:
        result = MoleculeRecord(
            name=self.name,
            sequence=self.sequence,
            topology=self.topology,
            features=list(self.features),
            primers=list(primers),
            source_format=self.source_format,
            metadata=dict(self.metadata),
        )
        result.validate()
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sequence": self.sequence,
            "length": self.length,
            "topology": self.topology,
            "features": [feature.to_dict() for feature in self.features],
            "primers": [primer.to_dict() for primer in self.primers],
            "source_format": self.source_format,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> MoleculeRecord:
        result = cls(
            name=str(value["name"]),
            sequence=str(value["sequence"]),
            topology=str(value.get("topology", "linear")),
            features=[Feature.from_dict(item) for item in value.get("features", [])],
            primers=[Primer.from_dict(item) for item in value.get("primers", [])],
            source_format=str(value.get("source_format", "unknown")),
            metadata=dict(value.get("metadata", {})),
        )
        result.validate()
        return result
