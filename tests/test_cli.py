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
    assert result["schema_version"] == "1"
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
