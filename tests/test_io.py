from pathlib import Path

import pytest

from snapgene_bridge.errors import InputError
from snapgene_bridge.io import read_record, write_record
from snapgene_bridge.models import MoleculeRecord, Primer


def test_fasta_round_trip(tmp_path: Path):
    source = tmp_path / "input.fasta"
    source.write_text(">plasmid example\nacgtacgt\n")
    record = read_record(source)

    assert record.name == "plasmid"
    assert record.sequence == "ACGTACGT"
    assert record.source_format == "fasta"

    output = tmp_path / "output.fasta"
    report = write_record(record, output)
    assert report.format == "fasta"
    assert read_record(output).sequence == record.sequence
    assert report.warnings


def test_output_is_not_overwritten_without_force(tmp_path: Path):
    source = tmp_path / "input.fasta"
    source.write_text(">fixture\nACGT\n")
    record = read_record(source)

    with pytest.raises(InputError, match="overwrite"):
        write_record(record, source)


def test_fasta_output_warns_about_annotations(tmp_path: Path):
    record = MoleculeRecord(
        name="fixture",
        sequence="ACGTACGT",
        primers=[Primer(name="F", sequence="ACGT")],
    )
    report = write_record(record, tmp_path / "fixture.fa")
    assert "does not preserve" in report.warnings[0]


def test_snapgene_file_reports_strongest_site_and_its_origin(data_dir):
    record = read_record(data_dir / "regression6.snapgene-8.0.0.dna")
    primers = {p.name: p for p in record.primers}
    assert record.length == 3000 and len(primers) == 6
    p2 = primers["P2_rev_perfect"]  # also has a weak 11 nt site with Tm 33
    assert (p2.binding_start, p2.binding_end, p2.strand, p2.tm_celsius) == (1500, 1524, "-", 62.0)
    assert p2.tm_standard == "snapgene-file"


def test_genbank_output_is_snapgene_flavoured_and_reads_back(tmp_path: Path):
    record = MoleculeRecord(
        name="fixture",
        sequence="ACGT" * 20,
        primers=[Primer(name="F", sequence="ACGTACGTACGTAC")],
    )
    report = write_record(record, tmp_path / "out.gb")
    text = (tmp_path / "out.gb").read_text()
    assert report.format == "genbank-snapgene"
    assert "from SnapGene" in text and "sequence: ACGTACGTACGTAC" in text
    again = read_record(tmp_path / "out.gb")
    assert [p.name for p in again.primers] == ["F"] and again.features == []
