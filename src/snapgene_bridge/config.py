"""Client configuration: where the SnapGene node is and how to reach it.

File: ``~/.config/snapgene-bridge/config.toml`` (override the path with
``SNAPGENE_BRIDGE_CONFIG``).  Environment variables ``SNAPGENE_BRIDGE_MODE``,
``SNAPGENE_BRIDGE_HOST`` and ``SNAPGENE_BRIDGE_NODE_DIR`` override the file.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import InputError

DEFAULT_PATH = Path("~/.config/snapgene-bridge/config.toml")
MODES = ("ssh", "local", "off")


@dataclass
class NodeConfig:
    """Modes: ``ssh`` (node over SSH), ``local`` (SnapGene here), ``off`` (estimates only)."""

    mode: str = "off"
    host: str | None = None
    dir: str = "~/snapgene-bridge-node"
    snapgene_exe: str | None = None
    scratch_dir: str | None = None
    timeout_s: int = 300
    ssh_options: list[str] = field(
        default_factory=lambda: ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
    )
    path: str | None = None

    def node_settings(self) -> dict:
        """Settings forwarded to the node with every request."""

        return {
            key: value
            for key, value in (
                ("snapgene_exe", self.snapgene_exe),
                ("scratch_dir", self.scratch_dir),
                ("timeout_s", self.timeout_s),
            )
            if value
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "host": self.host,
            "dir": self.dir,
            "snapgene_exe": self.snapgene_exe,
            "scratch_dir": self.scratch_dir,
            "timeout_s": self.timeout_s,
            "config_path": self.path,
        }


def config_path() -> Path:
    return Path(os.environ.get("SNAPGENE_BRIDGE_CONFIG", str(DEFAULT_PATH))).expanduser()


def load_config(path: Path | None = None) -> NodeConfig:
    source = path or config_path()
    data: dict = {}
    if source.exists():
        try:
            data = tomllib.loads(source.read_text()).get("node", {})
        except tomllib.TOMLDecodeError as error:
            raise InputError(f"Cannot parse {source}: {error}") from error
    cfg = NodeConfig(path=str(source) if source.exists() else None)
    for key in ("mode", "host", "dir", "snapgene_exe", "scratch_dir"):
        if data.get(key):
            setattr(cfg, key, str(data[key]))
    if data.get("timeout_s"):
        cfg.timeout_s = int(data["timeout_s"])
    if isinstance(data.get("ssh_options"), list):
        cfg.ssh_options = [str(item) for item in data["ssh_options"]]
    env = os.environ
    cfg.host = env.get("SNAPGENE_BRIDGE_HOST", cfg.host)
    cfg.dir = env.get("SNAPGENE_BRIDGE_NODE_DIR", cfg.dir)
    explicit_mode = env.get("SNAPGENE_BRIDGE_MODE") or data.get("mode")
    if explicit_mode:
        cfg.mode = str(explicit_mode)
    elif cfg.host:
        cfg.mode = "ssh"
    if cfg.mode not in MODES:
        raise InputError(
            f"Unknown node mode {cfg.mode!r}.", hint=f"Use one of: {', '.join(MODES)}."
        )
    return cfg


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def save_config(cfg: NodeConfig, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# snapgene-bridge client configuration", "[node]"]
    for key in ("mode", "host", "dir", "snapgene_exe", "scratch_dir", "timeout_s", "ssh_options"):
        value = getattr(cfg, key)
        if value not in (None, "", []):
            lines.append(f"{key} = {_toml_value(value)}")
    target.write_text("\n".join(lines) + "\n")
    return target
