import base64
import json
import re

import pytest

from snapgene_bridge.config import NodeConfig, load_config, save_config
from snapgene_bridge.errors import NodeNotConfiguredError, SnapGeneBusyError
from snapgene_bridge.protocol import BEGIN, END, frame, unframe
from snapgene_bridge.transport import build_request_script, call_node, remote_dir_expression


def test_unframe_ignores_shell_noise():
    noisy = "Welcome!\n" + frame({"ok": True, "x": 1}) + "logout\n"
    assert unframe(noisy) == {"ok": True, "x": 1, "protocol": 1}
    assert unframe("logout\n") is None


def test_remote_dir_expression_expands_home_only():
    assert remote_dir_expression("~/snapgene-bridge-node") == '"$HOME"/snapgene-bridge-node'
    assert remote_dir_expression("/opt/x y") == "'/opt/x y'"


def test_request_script_carries_payload_as_base64():
    cfg = NodeConfig(mode="ssh", host="node")
    request = {"op": "evaluate", "jobs": [{"name": "a!b", "sequence": "ACGT"}]}
    script = build_request_script(cfg, request)
    assert script.startswith("set +H")
    body = re.search(r"<<'SGB_REQUEST_EOF'\n(.*?)\nSGB_REQUEST_EOF", script, re.S).group(1)
    assert json.loads(base64.b64decode(body.replace("\n", ""))) == request
    assert all(len(line) <= 76 for line in body.splitlines())
    assert "a!b" not in script  # nothing user-supplied reaches the shell unencoded
    assert BEGIN in script and END in script  # not-deployed fallback answer


def test_off_mode_requires_node_or_offline():
    with pytest.raises(NodeNotConfiguredError):
        call_node(NodeConfig(mode="off"), {"op": "ping"})


def test_node_errors_are_rebuilt_as_typed_errors(monkeypatch):
    import snapgene_bridge.node.__main__ as node_main

    monkeypatch.setattr(
        node_main,
        "handle",
        lambda request: {"ok": False, "error": {"code": "snapgene_busy", "message": "open"}},
    )
    with pytest.raises(SnapGeneBusyError):
        call_node(NodeConfig(mode="local"), {"op": "evaluate"})


def test_config_round_trip_and_env_override(tmp_path, monkeypatch):
    path = tmp_path / "c.toml"
    save_config(NodeConfig(mode="ssh", host="lab-node", timeout_s=120), path)
    cfg = load_config(path)
    assert (cfg.mode, cfg.host, cfg.timeout_s) == ("ssh", "lab-node", 120)
    monkeypatch.setenv("SNAPGENE_BRIDGE_HOST", "other")
    assert load_config(path).host == "other"
