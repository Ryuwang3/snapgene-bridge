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
