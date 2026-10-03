import json
from importlib import resources

from snapgene_bridge.node import backends, runner


def test_parse_dna_result_matches_snapgene_8_output(data_dir):
    """The fixture .dna was written by SnapGene 8.0.0; parsing must reproduce its sites."""

    expected = json.loads(
        resources.files("snapgene_bridge.selftest_data").joinpath("regression6.json").read_text()
    )["expected"]
    parsed = runner.parse_dna_result(data_dir / "regression6.snapgene-8.0.0.dna")
    assert set(parsed) == set(expected)
    for name, info in expected.items():

        def key(site):
            return (site["start"], site["end"], site["strand"], site["tm"], site["annealed"])

        assert sorted(map(key, parsed[name])) == sorted(map(key, info["sites"])), name


def test_components_describe_tail_and_bulge(data_dir):
    parsed = runner.parse_dna_result(data_dir / "regression6.snapgene-8.0.0.dna")
    tail = parsed["P3_fwd_5tail"][0]["components"]
    assert tail[0] == {"bases": "GGATCCATGC"}  # unpaired 5' tail
    assert tail[1]["hybridized"] == [800, 820]
    bulge = [c["hybridized"] for c in parsed["P6_fwd_bulge"][0]["components"]]
    assert bulge == [[2500, 2512], [2513, 2524]]  # template base 2512 is skipped


def test_labels_are_unique_and_duplicates_share_one_primer():
    sent, owners = runner._labels(
        [
            {"name": "my primer", "sequence": "ACGTACGTAC"},
            {"name": "my/primer", "sequence": "TTTTGGGGCC"},
            {"name": "copy", "sequence": "acgtacgtac"},
        ]
    )
    assert [p["name"] for p in sent] == ["my_primer", "my_primer_2"]
    assert owners["my_primer"] == ["my primer", "copy"]


def test_tasklist_parsing(monkeypatch):
    sample = '"SnapGene.exe","41328","Console","1","95,124 K"\n"snapgene.exe","7","x","1","1 K"\n'
    monkeypatch.setattr(backends, "_run", lambda *a, **k: sample)
    assert backends.WslBackend("x").running_pids() == {41328, 7}
    monkeypatch.setattr(backends, "_run", lambda *a, **k: "INFO: No tasks are running.\n")
    assert backends.WslBackend("x").running_pids() == set()
