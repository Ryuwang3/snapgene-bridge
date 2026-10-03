"""Install or update the node side from this source checkout.

Builds a wheel locally, ships it over the same stdin-script SSH channel,
creates ``<node dir>/.venv`` on the node and installs the wheel there.  If the
node's proxy variables point at a dead proxy, the install is retried once
with them unset (seen on WSL nodes whose Windows proxy app is not running).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import __version__
from .config import NodeConfig
from .errors import NodeError, NodeNotConfiguredError, OperationUnavailableError
from .protocol import BEGIN, END, unframe
from .transport import _heredoc_payload, remote_dir_expression, run_script

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_wheel(out_dir: Path) -> Path:
    if not (REPO_ROOT / "pyproject.toml").exists():
        raise OperationUnavailableError(
            "deploy needs a source checkout of snapgene-bridge.",
            hint="Run deploy from the cloned repository, e.g. after `uv tool install -e .`.",
        )
    if shutil.which("uv"):
        command = ["uv", "build", "--wheel", "--out-dir", str(out_dir), str(REPO_ROOT)]
    else:
        command = ["python3", "-m", "pip", "wheel", "--no-deps", "-w", str(out_dir), str(REPO_ROOT)]
    completed = subprocess.run(command, capture_output=True, text=True)
    wheels = sorted(out_dir.glob("snapgene_bridge-*.whl"))
    if completed.returncode != 0 or not wheels:
        raise OperationUnavailableError(
            "Building the wheel failed.", details={"stderr": completed.stderr[-1500:]}
        )
    return wheels[-1]


def deploy_script(cfg: NodeConfig, wheel: Path) -> str:
    return (
        "set +H 2>/dev/null\n"
        f"SGB_DIR={remote_dir_expression(cfg.dir)}\n"
        'mkdir -p "$SGB_DIR/wheels"\n'
        f'SGB_TMP="$SGB_DIR/wheels/{wheel.name}"\n'
        + _heredoc_payload(wheel.read_bytes(), "SGB_WHEEL_EOF")
        + 'if [ ! -x "$SGB_DIR/.venv/bin/python" ]; then\n'
        '  if command -v uv >/dev/null 2>&1; then uv venv -q "$SGB_DIR/.venv"; '
        'else python3 -m venv "$SGB_DIR/.venv"; fi\n'
        "fi\n"
        "sgb_install() {\n"
        "  if command -v uv >/dev/null 2>&1; then\n"
        '    uv pip install -q --python "$SGB_DIR/.venv/bin/python" '
        '--reinstall-package snapgene-bridge "$SGB_TMP"\n'
        "  else\n"
        '    "$SGB_DIR/.venv/bin/python" -m pip install -q --force-reinstall --no-deps "$SGB_TMP" '
        '&& "$SGB_DIR/.venv/bin/python" -m pip install -q "$SGB_TMP"\n'
        "  fi\n"
        "}\n"
        'if ! sgb_install > "$SGB_DIR/install.log" 2>&1; then\n'
        "  ( unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY; "
        'sgb_install ) >> "$SGB_DIR/install.log" 2>&1 || '
        f"{{ printf '%s\\n' '{BEGIN}' "
        '\'{"ok": false, "error": {"code": "install_failed", "message": '
        '"Installing on the node failed; see install.log in the node directory."}}\' '
        f"'{END}'; tail -n 20 \"$SGB_DIR/install.log\"; exit 0; }}\n"
        "fi\n"
        'echo \'{"op": "status"}\' | "$SGB_DIR/.venv/bin/python" -m snapgene_bridge.node\n'
        "exit 0\n"
    )


def deploy(cfg: NodeConfig) -> dict:
    if cfg.mode != "ssh" or not cfg.host:
        raise NodeNotConfiguredError(
            "deploy needs an SSH node.",
            hint="Run: snapgene-bridge init --host <ssh-alias>",
        )
    with tempfile.TemporaryDirectory() as tmp:
        wheel = build_wheel(Path(tmp))
        completed = run_script(cfg, deploy_script(cfg, wheel), timeout=900)
    response = unframe(completed.stdout)
    if response is None or not response.get("ok"):
        message = (response or {}).get("error", {}).get("message", "No response from the node.")
        raise NodeError(
            f"Deploy failed: {message}",
            details={"stdout_tail": completed.stdout.strip()[-1500:]},
        )
    return {"wheel": wheel.name, "client_version": __version__, "node": response}
