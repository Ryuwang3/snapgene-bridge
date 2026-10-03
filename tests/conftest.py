import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def isolated_config(request, tmp_path, monkeypatch):
    """Unit tests never read the developer's real node config; node tests do."""

    if request.node.get_closest_marker("node"):
        return
    for key in ("SNAPGENE_BRIDGE_HOST", "SNAPGENE_BRIDGE_MODE", "SNAPGENE_BRIDGE_NODE_DIR"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SNAPGENE_BRIDGE_CONFIG", str(tmp_path / "config.toml"))


@pytest.fixture
def data_dir() -> Path:
    return DATA
