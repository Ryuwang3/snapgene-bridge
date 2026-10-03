"""Reach the SnapGene node.

Over SSH the request travels inside a small POSIX shell script on standard
input, never as a remote command argument.  Some nodes (Windows OpenSSH whose
default shell is WSL bash) drop remote command arguments, and a script on
stdin works the same way on ordinary Linux or macOS hosts.  Payloads are
base64 so no shell quoting or history expansion can alter them.
"""

from __future__ import annotations

import base64
import json
import shlex
import subprocess
import textwrap
from typing import Any

from .config import NodeConfig
from .errors import (
    NodeError,
    NodeNotConfiguredError,
    NodeUnreachableError,
    error_from_dict,
)
from .protocol import BEGIN, END, PROTOCOL_VERSION, unframe

_NOT_DEPLOYED = json.dumps(
    {
        "ok": False,
        "protocol": PROTOCOL_VERSION,
        "error": {
            "code": "node_not_deployed",
            "message": "snapgene-bridge is not installed on the node.",
            "hint": "Run: snapgene-bridge deploy",
        },
    }
)


def remote_dir_expression(path: str) -> str:
    """Shell expression for a node directory, expanding a leading ``~`` to ``$HOME``."""

    if path == "~":
        return '"$HOME"'
    if path.startswith("~/"):
        return '"$HOME"/' + shlex.quote(path[2:])
    return shlex.quote(path)


def _heredoc_payload(data: bytes, marker: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    body = "\n".join(textwrap.wrap(encoded, 76)) or ""
    return f"base64 -d > \"$SGB_TMP\" <<'{marker}'\n{body}\n{marker}\n"


def build_request_script(cfg: NodeConfig, request: dict[str, Any]) -> str:
    payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
    return (
        "set +H 2>/dev/null\n"
        f"SGB_DIR={remote_dir_expression(cfg.dir)}\n"
        'SGB_PY="$SGB_DIR/.venv/bin/python"\n'
        'if [ ! -x "$SGB_PY" ]; then\n'
        f"  printf '%s\\n' '{BEGIN}' '{_NOT_DEPLOYED}' '{END}'\n"
        "  exit 0\n"
        "fi\n"
        'SGB_TMP="$(mktemp)"\n'
        + _heredoc_payload(payload, "SGB_REQUEST_EOF")
        + '"$SGB_PY" -m snapgene_bridge.node < "$SGB_TMP"\n'
        'rm -f "$SGB_TMP"\n'
        "exit 0\n"
    )


def run_script(cfg: NodeConfig, script: str, timeout: float) -> subprocess.CompletedProcess:
    if not cfg.host:
        raise NodeNotConfiguredError(
            "No SnapGene node host is configured.",
            hint="Run: snapgene-bridge init --host <ssh-alias>",
        )
    command = ["ssh", "-T", *cfg.ssh_options, cfg.host]
    try:
        completed = subprocess.run(
            command, input=script, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as error:
        raise NodeUnreachableError("The ssh client is not installed.") from error
    except subprocess.TimeoutExpired as error:
        raise NodeUnreachableError(
            f"The node did not answer within {timeout:.0f} s.",
            hint="Check the network path, or raise timeout_s in the config.",
        ) from error
    if completed.returncode == 255:
        raise NodeUnreachableError(
            f"SSH to {cfg.host!r} failed.",
            hint="Check that `ssh <host>` works without a password prompt.",
            details={"stderr": completed.stderr.strip()[-800:]},
        )
    return completed


def call_node(cfg: NodeConfig, request: dict[str, Any], timeout: float | None = None) -> dict:
    """Send one request; return the node's response or raise its error."""

    body = {"protocol": PROTOCOL_VERSION, "node": cfg.node_settings(), **request}
    if cfg.mode == "local":
        from .node.__main__ import handle

        response = handle(body)
    elif cfg.mode == "ssh":
        completed = run_script(cfg, build_request_script(cfg, body), timeout or cfg.timeout_s + 90)
        response = unframe(completed.stdout)
        if response is None:
            raise NodeError(
                "The node returned no framed response.",
                hint="Run `snapgene-bridge status`; if it persists, run `snapgene-bridge deploy`.",
                details={
                    "stdout_tail": completed.stdout.strip()[-800:],
                    "stderr_tail": completed.stderr.strip()[-800:],
                },
            )
    else:
        raise NodeNotConfiguredError(
            "No SnapGene node is configured, so SnapGene cannot compute Tm or binding sites.",
            hint="Run `snapgene-bridge init --host <ssh-alias>` then `snapgene-bridge deploy`, "
            "or pass --offline to use local estimates.",
        )
    if not response.get("ok"):
        error = response.get("error") or {"message": "Unknown node error."}
        if error.get("code") == "node_not_deployed":
            raise NodeError(error["message"], hint=error.get("hint"))
        raise error_from_dict(error)
    return response
