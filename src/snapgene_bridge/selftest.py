"""Regression check of the node against values SnapGene 8.0.0 produced.

SnapGene is deterministic, so any difference means the SnapGene version, its
hybridization preferences, or the bridge changed.  Run after every SnapGene
update and every deploy.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .models import MoleculeRecord
from .oracle import SnapGeneOracle

SUITES = ("regression6", "puc19_bla", "random200")


def load_suite(name: str) -> dict[str, Any]:
    text = resources.files("snapgene_bridge.selftest_data").joinpath(f"{name}.json").read_text()
    return json.loads(text)


def _key(site: dict[str, Any]) -> tuple:
    return (site["start"], site["end"], site["strand"], site["tm"])


def check_suite(name: str, suite: dict[str, Any], verdicts: dict[str, Any]) -> list[str]:
    """Return human-readable mismatches between expected and observed results."""

    problems = []
    for primer in suite["primers"]:
        expected = suite["expected"][primer["name"]]
        verdict = verdicts.get(primer["name"])
        if verdict is None:
            problems.append(f"{primer['name']}: missing from the node response")
            continue
        if verdict.imported != expected["imported"]:
            problems.append(
                f"{primer['name']}: imported={verdict.imported}, expected {expected['imported']}"
            )
            continue
        observed = sorted(_key(vars(site)) for site in verdict.sites)
        if "sites" in expected:
            wanted = sorted(_key(site) for site in expected["sites"])
            if observed != wanted:
                problems.append(f"{primer['name']}: sites {observed} != expected {wanted}")
        elif "main" in expected:
            main = expected["main"]
            wanted_main = _key(main)
            others = sorted((s[0], s[1], s[2], s[3]) for s in expected["other_sites"])
            if wanted_main not in observed:
                problems.append(f"{primer['name']}: main site {wanted_main} not in {observed}")
            elif sorted(set(observed) - {wanted_main}) != others:
                problems.append(f"{primer['name']}: extra sites differ: {observed}")
    return problems


def run_selftest(oracle: SnapGeneOracle, quick: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {"suites": [], "passed": True}
    for name in SUITES:
        suite = load_suite(name)
        primers = suite["primers"][:40] if quick and name == "random200" else suite["primers"]
        record = MoleculeRecord(name=name, sequence=suite["template"], topology=suite["topology"])
        run = oracle.evaluate(record, primers)
        problems = check_suite(name, {**suite, "primers": primers}, run.verdicts)
        report["suites"].append(
            {
                "suite": name,
                "description": suite["description"],
                "primers": len(primers),
                "expected_snapgene_version": suite["snapgene_version"],
                "observed": run.meta(),
                "passed": not problems,
                "mismatches": problems[:20],
                "mismatch_count": len(problems),
            }
        )
        report["passed"] = report["passed"] and not problems
    return report
