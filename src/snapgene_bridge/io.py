"""Format adapters for FASTA, GenBank, and SnapGene files.

Optional libraries are imported only when their format is requested.  A plain
installation can therefore still run ``status`` and inspect FASTA files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import (
    DependencyMissingError,
    InputError,
    UnsupportedFormatError,
)
from .models import Feature, MoleculeRecord, Primer, Segment

FASTA_SUFFIXES = {".fa", ".fasta", ".fna"}
GENBANK_SUFFIXES = {".gb", ".gbk", ".genbank"}
SNAPGENE_SUFFIXES = {".dna"}


@dataclass(frozen=True)
class WriteReport:
    path: str
    format: str
    warnings: tuple[str, ...] = ()


def _dependency(name: str, extra: str, error: Exception) -> DependencyMissingError:
    return DependencyMissingError(
        f"Reading or writing this format requires optional dependency {name!r}.",
        hint=f"{name} is a declared dependency; reinstall snapgene-bridge.",
    )


def read_record(path: str | Path) -> MoleculeRecord:
    """Read one molecule from a supported file."""

    source = Path(path).expanduser()
    if not source.exists():
        raise InputError(f"Input file does not exist: {source}")
    if not source.is_file():
        raise InputError(f"Input path is not a file: {source}")

    suffix = source.suffix.lower()
    if suffix in FASTA_SUFFIXES:
        return _read_fasta(source)
    if suffix in GENBANK_SUFFIXES:
        return _read_genbank(source)
    if suffix in SNAPGENE_SUFFIXES:
        return _read_snapgene(source)
    raise UnsupportedFormatError(
        f"Unsupported input format {source.suffix or '<none>'!r}.",
        hint="Use .dna, .gb, .gbk, .genbank, .fa, or .fasta.",
    )


def write_record(
    record: MoleculeRecord,
    path: str | Path,
    *,
    force: bool = False,
) -> WriteReport:
    """Write a molecule without replacing an existing file by default."""

    record.validate()
    target = Path(path).expanduser()
    if target.exists() and not force:
        raise InputError(
            f"Refusing to overwrite existing output: {target}",
            hint="Choose a new output path or pass --force explicitly.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)

    suffix = target.suffix.lower()
    if suffix in FASTA_SUFFIXES:
        target.write_text(f">{record.name}\n{_wrap_sequence(record.sequence)}\n")
        warnings = ("FASTA does not preserve features or primers.",)
        return WriteReport(str(target), "fasta", warnings)
    if suffix in GENBANK_SUFFIXES:
        return _write_genbank(record, target)
    if suffix in SNAPGENE_SUFFIXES:
        return _write_snapgene(record, target)
    raise UnsupportedFormatError(
        f"Unsupported output format {target.suffix or '<none>'!r}.",
        hint="Use .dna, .gb, .gbk, .genbank, .fa, or .fasta.",
    )


def _wrap_sequence(sequence: str, width: int = 80) -> str:
    return "\n".join(sequence[index : index + width] for index in range(0, len(sequence), width))


def _read_fasta(source: Path) -> MoleculeRecord:
    header: str | None = None
    sequence_lines: list[str] = []
    records = 0
    for raw_line in source.read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            records += 1
            if records > 1:
                raise InputError(
                    f"FASTA input contains multiple records: {source}",
                    hint="Pass one molecule per file for the bridge MVP.",
                )
            header = line[1:].strip()
            continue
        if header is None:
            raise InputError("FASTA sequence appeared before its header.")
        sequence_lines.append(line)
    if not header:
        raise InputError(f"FASTA input has no header: {source}")
    name, _, description = header.partition(" ")
    return MoleculeRecord(
        name=name or source.stem,
        sequence="".join(sequence_lines),
        source_format="fasta",
        metadata={"description": description},
    )


def _read_genbank(source: Path) -> MoleculeRecord:
    try:
        from Bio import SeqIO
    except ImportError as error:  # pragma: no cover - exercised by environment
        raise _dependency("biopython", "bio", error) from error

    records = list(SeqIO.parse(str(source), "genbank"))
    if len(records) != 1:
        raise InputError(
            f"Expected one GenBank record, found {len(records)} in {source}.",
            hint="Pass one molecule per file for the bridge MVP.",
        )
    parsed = records[0]
    features: list[Feature] = []
    primers: list[Primer] = []
    for item in parsed.features:
        if item.location is None or item.type == "source":
            continue
        segments = tuple(Segment(int(part.start), int(part.end)) for part in item.location.parts)
        qualifiers: dict[str, Any] = {}
        for key, values in item.qualifiers.items():
            qualifiers[key] = values[0] if len(values) == 1 else list(values)
        label = (
            qualifiers.get("label")
            or qualifiers.get("gene")
            or qualifiers.get("locus_tag")
            or item.type
        )
        strand = (
            "." if item.location.strand is None else ("+" if item.location.strand >= 0 else "-")
        )
        primer_sequence = _snapgene_primer_sequence(item.qualifiers.get("note", []))
        if item.type == "primer_bind" and primer_sequence:
            primers.append(Primer(name=str(label), sequence=primer_sequence))
            continue
        features.append(
            Feature(
                name=str(label),
                type=item.type or "misc_feature",
                segments=segments,
                strand=strand,
                qualifiers=qualifiers,
            )
        )
    record = MoleculeRecord(
        name=parsed.name or parsed.id or source.stem,
        sequence=str(parsed.seq),
        topology="circular" if parsed.annotations.get("topology") == "circular" else "linear",
        features=features,
        primers=primers,
        source_format="genbank",
        metadata={
            "description": parsed.description,
            "annotations": {key: str(value) for key, value in parsed.annotations.items()},
        },
    )
    record.validate()
    return record


def _read_snapgene(source: Path) -> MoleculeRecord:
    try:
        import sgffp
    except ImportError as error:  # pragma: no cover - exercised by environment
        raise _dependency("sgffp", "snapgene", error) from error

    try:
        parsed = sgffp.SgffReader.from_file(source)
        length = len(parsed.sequence.value)
        features: list[Feature] = []
        for item in parsed.features:
            if not item.segments:
                continue
            segments: list[Segment] = []
            for part in item.segments:
                start, end = int(part.start), int(part.end)
                if end > start:
                    segments.append(Segment(start, end))
                else:  # origin-spanning segment on a circular molecule
                    segments.append(Segment(start, length))
                    if end > 0:
                        segments.append(Segment(0, end))
            features.append(
                Feature(
                    name=item.name or item.type or "feature",
                    type=item.type or "misc_feature",
                    segments=tuple(segments),
                    strand=item.strand if item.strand in {"+", "-"} else ".",
                    qualifiers=dict(item.qualifiers or {}),
                )
            )

        primers: list[Primer] = []
        for item in parsed.primers:
            # the strongest site is the intended one; weaker ones are off-target matches
            site = max(
                (candidate for candidate in item.binding_sites if not candidate.simplified),
                key=lambda candidate: candidate.melting_temperature or 0.0,
                default=None,
            )
            primers.append(
                Primer(
                    name=item.name or "primer",
                    sequence=item.sequence,
                    strand=(site.bound_strand if site else "+"),
                    binding_start=(site.start if site else None),
                    binding_end=(site.end if site else None),
                    tm_celsius=(site.melting_temperature if site else None),
                    tm_standard="snapgene-file" if site else "unknown",
                )
            )
        record = MoleculeRecord(
            name=source.stem,
            sequence=parsed.sequence.value,
            topology=parsed.sequence.topology,
            features=features,
            primers=primers,
            source_format="snapgene",
            metadata={"sgffp_block_types": list(parsed.types)},
        )
        record.validate()
        return record
    except Exception as error:
        if isinstance(error, (InputError, DependencyMissingError)):
            raise
        raise InputError(f"Could not parse SnapGene file {source}: {error}") from error


def _write_snapgene(record: MoleculeRecord, target: Path) -> WriteReport:
    try:
        import sgffp
    except ImportError as error:  # pragma: no cover - exercised by environment
        raise _dependency("sgffp", "snapgene", error) from error

    try:
        sgff = sgffp.SgffObject.new(
            record.sequence,
            topology=record.topology,
            strandedness="double",
            sequence_type="dna",
        )
        for feature in record.features:
            sgff.features.add(
                sgffp.SgffFeature(
                    name=feature.name,
                    type=feature.type,
                    strand=feature.strand if feature.strand in {"+", "-"} else "+",
                    segments=[
                        sgffp.SgffSegment(start=segment.start, end=segment.end)
                        for segment in feature.segments
                    ],
                    qualifiers=dict(feature.qualifiers),
                )
            )
        for primer in record.primers:
            # No binding sites: stored sites would carry a Tm SnapGene did not compute.
            sgff.primers.add(sgffp.SgffPrimer(name=primer.name, sequence=primer.sequence))
        sgffp.SgffWriter.to_file(sgff, target)
    except Exception as error:
        raise InputError(f"Could not write SnapGene file {target}: {error}") from error
    warnings = ()
    if record.primers:
        warnings = (
            "Primers are stored without binding sites; SnapGene computes them when the file is "
            "opened. Prefer `--output` with a configured node for a SnapGene-generated file.",
        )
    return WriteReport(str(target), "snapgene", warnings)


def _write_genbank(record: MoleculeRecord, target: Path) -> WriteReport:
    """Write SnapGene-flavoured GenBank: SnapGene imports the primers and computes their sites."""

    from .snapgene_genbank import write_snapgene_genbank

    text = write_snapgene_genbank(
        name=record.name,
        sequence=record.sequence,
        topology=record.topology,
        features=[
            {
                "name": f.name,
                "type": f.type,
                "strand": f.strand,
                "segments": [{"start": seg.start, "end": seg.end} for seg in f.segments],
            }
            for f in record.features
        ],
        primers=[{"name": p.name, "sequence": p.sequence} for p in record.primers],
    )
    target.write_text(text)
    return WriteReport(str(target), "genbank-snapgene")


def _snapgene_primer_sequence(notes: list[str]) -> str | None:
    """Primer sequence from SnapGene's ``/note="color: ...; sequence: ..."`` convention."""

    if not notes:
        return None
    for part in str(notes[-1]).replace("\n", " ").split(";"):
        key, _, value = part.partition(":")
        if key.strip().lower() == "sequence" and value.strip():
            return "".join(value.split()).upper()
    return None
