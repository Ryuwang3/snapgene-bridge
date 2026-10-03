import json
from pathlib import Path

from snapgene_bridge.cli import main


def _last_json(capsys):
    return json.loads(capsys.readouterr().out)


def test_read_command_returns_stable_json(capsys, tmp_path: Path):
    source = tmp_path / "fixture.fasta"
    source.write_text(">fixture\nACGTACGT\n")

    assert main(["read", str(source)]) == 0
    result = _last_json(capsys)

    assert result["ok"] is True
    assert result["schema_version"] == "2"
    assert result["command"] == "read"
    assert result["record"]["length"] == 8


def test_missing_input_is_json_error(capsys, tmp_path: Path):
    assert main(["read", str(tmp_path / "missing.fasta")]) == 2
    result = _last_json(capsys)

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_input"


def test_open_dry_run_does_not_spawn_process(capsys, tmp_path: Path):
    source = tmp_path / "fixture.fasta"
    source.write_text(">fixture\nACGT\n")

    assert main(["open", str(source), "--dry-run"]) == 0
    result = _last_json(capsys)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["command"] == "open"
    assert result["launch_command"]


def test_check_offline_reports_estimates(capsys, data_dir):
    code = main(
        [
            "check",
            str(data_dir / "regression6.snapgene-8.0.0.dna"),
            "--primer",
            "P1=CCAGCTTCTTTCCCGAAGTGTG",
            "--offline",
        ]
    )
    result = _last_json(capsys)
    assert code == 0 and result["tm_standard"] == "estimate:nn"
    site = result["primers"][0]["sites"][0]
    assert (site["location"], site["strand"]) == ("501..522", "+")


def test_design_without_node_explains_next_step(capsys, data_dir):
    code = main(["clone", str(data_dir / "pUC19_L09137.gb"), "--region", "1626..2486"])
    result = _last_json(capsys)
    assert code == 2 and result["error"]["code"] == "node_not_configured"
    assert "--offline" in result["error"]["hint"]


def test_clone_offline_writes_genbank_and_order_sheet(capsys, data_dir, tmp_path: Path):
    output, order = tmp_path / "bla.gb", tmp_path / "order.tsv"
    code = main(
        [
            "clone",
            str(data_dir / "pUC19_L09137.gb"),
            "--region",
            "1626..2486",
            "--strand",
            "-",
            "--tail-f",
            "GCGCTAGC",
            "--tail-r",
            "GCCTCGAG",
            "--name",
            "bla",
            "--offline",
            "--output",
            str(output),
            "--order",
            str(order),
        ]
    )
    result = _last_json(capsys)
    assert code == 0, result
    assert result["design"]["region"]["insert_length"] == 861
    assert "from SnapGene" in output.read_text()
    assert order.read_text().count("\n") == 3
    assert result["warnings"]  # offline values are flagged


def test_init_and_status_without_node(capsys):
    assert main(["init", "--host", "example-node"]) == 0
    init = _last_json(capsys)
    assert init["config"]["mode"] == "ssh" and init["config"]["host"] == "example-node"
    assert main(["status", "--no-node"]) == 0
    status = _last_json(capsys)
    assert status["config"]["host"] == "example-node" and status["ready"] is False
