"""End-to-end checks against a real SnapGene node.  Run with: pytest -m node"""

import pytest

from snapgene_bridge.config import load_config
from snapgene_bridge.oracle import SnapGeneOracle
from snapgene_bridge.selftest import run_selftest

pytestmark = pytest.mark.node


@pytest.fixture(scope="module")
def oracle():
    cfg = load_config()
    if cfg.mode == "off":
        pytest.skip("no SnapGene node configured")
    return SnapGeneOracle(cfg)


def test_node_is_ready(oracle):
    info = oracle.status()
    assert info["snapgene_found"], info
    assert not info["snapgene_running_pids"], "close SnapGene on the node"


def test_selftest_matches_snapgene_8(oracle):
    report = run_selftest(oracle)
    failures = [s for s in report["suites"] if not s["passed"]]
    assert not failures, failures
