import datetime

from Bio import SeqIO

from snapgene_bridge.snapgene_genbank import write_snapgene_genbank

TEMPLATE = "ACGT" * 30


def _write(tmp_path, **kwargs):
    text = write_snapgene_genbank(
        name=kwargs.pop("name", "job one"),
        sequence=kwargs.pop("sequence", TEMPLATE),
        today=datetime.date(2026, 10, 3),
        **kwargs,
    )
    path = tmp_path / "job.gb"
    path.write_text(text)
    return text, path


def test_journal_line_marks_snapgene_flavour(tmp_path):
    text, _ = _write(tmp_path)
    assert "  JOURNAL   Exported Oct 3, 2026 from SnapGene 8.0.0\n" in text
    assert text.startswith("LOCUS       job_one ")


def test_primers_use_snapgene_note_convention(tmp_path):
    text, path = _write(
        tmp_path, primers=[{"name": "P1", "sequence": "acgtacgtacgtac"}], topology="circular"
    )
    assert "     primer_bind     1..14\n" in text
    assert "/label=P1\n" in text
    assert '/note="color: black; sequence: ACGTACGTACGTAC"' in text
    record = SeqIO.read(path, "genbank")
    assert record.annotations["topology"] == "circular"
    assert str(record.seq) == TEMPLATE


def test_long_primer_sequence_is_never_split(tmp_path):
    long_primer = "GATTACA" * 12  # 84 nt, longer than one qualifier line
    text, path = _write(tmp_path, primers=[{"name": "long", "sequence": long_primer}])
    assert long_primer in text  # kept as one unbroken token
    note = SeqIO.read(path, "genbank").features[1].qualifiers["note"][0]
    assert note.replace(" ", "").endswith(long_primer)


def test_features_split_at_origin_and_keep_strand(tmp_path):
    features = [
        {"name": "ori-span", "type": "CDS", "strand": "-", "segments": [{"start": 110, "end": 10}]},
        {
            "name": "two parts",
            "type": "my feature",
            "strand": "+",
            "segments": [{"start": 20, "end": 30}, {"start": 40, "end": 41}],
        },
        {"name": "odd", "type": "bad/type!", "strand": ".", "segments": [{"start": 50, "end": 60}]},
    ]
    text, path = _write(tmp_path, features=features, topology="circular")
    assert "     CDS             complement(join(111..120,1..10))\n" in text
    assert "     my_feature      join(21..30,41)\n" in text
    assert "     misc_feature    51..60\n" in text  # invalid key falls back
    parsed = SeqIO.read(path, "genbank")
    assert [f.type for f in parsed.features] == ["source", "CDS", "my_feature", "misc_feature"]
