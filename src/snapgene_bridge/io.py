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
        hint=f"Install it with: uv sync --extra {extra}",
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
    for item in parsed.features:
        if item.location is None:
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
        features: list[Feature] = []
        for item in parsed.features:
            if not item.segments:
                continue
            features.append(
                Feature(
                    name=item.name or item.type or "feature",
                    type=item.type or "misc_feature",
                    segments=tuple(Segment(int(s.start), int(s.end)) for s in item.segments),
                    strand=item.strand if item.strand in {"+", "-"} else ".",
                    qualifiers=dict(item.qualifiers or {}),
                )
            )

        primers: list[Primer] = []
        for item in parsed.primers:
            site = next(
                (candidate for candidate in item.binding_sites if not candidate.simplified), None
            )
            primers.append(
                Primer(
                    name=item.name or "primer",
                    sequence=item.sequence,
                    strand=(site.bound_strand if site else "+"),
                    binding_start=(site.start if site else None),
                    binding_end=(site.end if site else None),
                    tm_celsius=(site.melting_temperature if site else None),
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
            binding_sites = []
            if primer.binding_start is not None and primer.binding_end is not None:
                binding_sites.append(
                    sgffp.SgffBindingSite(
                        start=primer.binding_start,
                        end=primer.binding_end,
                        bound_strand=primer.strand,
                        annealed_bases=primer.sequence,
                        melting_temperature=primer.tm_celsius,
                    )
                )
            sgff.primers.add(
                sgffp.SgffPrimer(
                    name=primer.name,
                    sequence=primer.sequence,
                    binding_sites=binding_sites,
                )
            )
        sgffp.SgffWriter(target).write(sgff)
    except Exception as error:
        raise InputError(f"Could not write SnapGene file {target}: {error}") from error
    return WriteReport(str(target), "snapgene")


def _write_genbank(record: MoleculeRecord, target: Path) -> WriteReport:
    try:
        from Bio import SeqIO
        from Bio.Seq import Seq
        from Bio.SeqFeature import CompoundLocation, SeqFeature, SimpleLocation
        from Bio.SeqRecord import SeqRecord
    except ImportError as error:  # pragma: no cover - exercised by environment
        raise _dependency("biopython", "bio", error) from error

    annotations = dict(record.metadata.get("annotations", {}))
    annotations["molecule_type"] = "DNA"
    annotations["topology"] = record.topology
    output = SeqRecord(
        Seq(record.sequence),
        id=record.name,
        name=record.name,
        description=str(record.metadata.get("description", "")),
        annotations=annotations,
    )
    for feature in record.features:
        locations = [
            SimpleLocation(
                segment.start,
                segment.end,
                strand=(1 if feature.strand == "+" else -1 if feature.strand == "-" else None),
            )
            for segment in feature.segments
        ]
        location = locations[0] if len(locations) == 1 else CompoundLocation(locations)
        qualifiers = {
            key: (value if isinstance(value, list) else [str(value)])
            for key, value in feature.qualifiers.items()
        }
        qualifiers.setdefault("label", [feature.name])
        output.features.append(
            SeqFeature(location=location, type=feature.type, qualifiers=qualifiers)
        )
    for primer in record.primers:
        if primer.binding_start is None or primer.binding_end is None:
            continue
        location = SimpleLocation(
            primer.binding_start,
            primer.binding_end,
            strand=1 if primer.strand == "+" else -1,
        )
        qualifiers = {
            "label": [primer.name],
            "sequence": [primer.sequence],
            "tm_standard": [primer.tm_standard],
        }
        if primer.tm_celsius is not None:
            qualifiers["tm_celsius"] = [str(primer.tm_celsius)]
        output.features.append(
            SeqFeature(location=location, type="primer_bind", qualifiers=qualifiers)
        )
    SeqIO.write(output, str(target), "genbank")
    return WriteReport(str(target), "genbank")
