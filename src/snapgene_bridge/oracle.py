"""Ask "where does this primer bind and at what Tm?".

``SnapGeneOracle`` sends the question to a SnapGene node and returns
SnapGene's own answer (``tm_standard`` = ``snapgene-<version>``).
``EstimateOracle`` is the offline fallback: an exact 3'-anchored search plus
the local nearest-neighbour estimate.  It misses mismatched or bulged sites
that SnapGene would report, and its values are labelled ``estimate:nn``.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .config import NodeConfig
from .models import MoleculeRecord
from .seqtools import format_location, revcomp, window
from .tm import ESTIMATE_STANDARD, estimate_tm
from .transport import call_node

SNAPGENE_MIN_TM = 40.0  # SnapGene's default hybridization threshold


@dataclass
class Site:
    start: int
    end: int
    strand: str
    tm: float | None
    annealed: str
    components: list[dict[str, Any]] = field(default_factory=list)

    def three_prime(self, length: int) -> int:
        """Template position just past the primer's 3' end (top-strand coordinates)."""

        return self.end % length if self.strand == "+" else self.start % length

    def to_dict(self, length: int) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "location": format_location(self.start, self.end, length),
            "strand": self.strand,
            "tm": self.tm,
            "annealed_length": len(self.annealed),
            "annealed": self.annealed,
            "components": self.components,
        }


@dataclass
class Verdict:
    name: str
    sequence: str
    imported: bool
    sites: list[Site]


@dataclass
class OracleRun:
    verdicts: dict[str, Verdict]
    tm_standard: str
    source: str
    elapsed_s: float | None = None
    snapgene: dict[str, Any] | None = None
    dna: bytes | None = None

    def meta(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "tm_standard": self.tm_standard,
            "elapsed_s": self.elapsed_s,
            "snapgene": self.snapgene,
            "primers_evaluated": len(self.verdicts),
        }


def _features(record: MoleculeRecord) -> list[dict[str, Any]]:
    return [
        {
            "name": f.name,
            "type": f.type,
            "strand": f.strand,
            "segments": [{"start": s.start, "end": s.end} for s in f.segments],
        }
        for f in record.features
    ]


class SnapGeneOracle:
    def __init__(self, cfg: NodeConfig):
        self.cfg = cfg

    def status(self) -> dict[str, Any]:
        return call_node(self.cfg, {"op": "status"}, timeout=120)

    def evaluate(
        self,
        record: MoleculeRecord,
        primers: Sequence[dict[str, Any]],
        *,
        return_dna: bool = False,
        include_features: bool = False,
    ) -> OracleRun:
        job = {
            "name": record.name,
            "sequence": record.sequence,
            "topology": record.topology,
            "features": _features(record) if include_features else [],
            "primers": [
                {"name": p["name"], "sequence": p["sequence"], "hint": p.get("hint")}
                for p in primers
            ],
            "return_dna": return_dna,
        }
        response = call_node(self.cfg, {"op": "evaluate", "jobs": [job]})
        result = response["jobs"][0]
        verdicts = {
            item["name"]: Verdict(
                name=item["name"],
                sequence=item["sequence"],
                imported=item["imported"],
                sites=[Site(**site) for site in item["sites"]],
            )
            for item in result["primers"]
        }
        version = (response.get("snapgene") or {}).get("version") or "unknown"
        dna = base64.b64decode(result["dna_base64"]) if result.get("dna_base64") else None
        return OracleRun(
            verdicts=verdicts,
            tm_standard=f"snapgene-{version}",
            source="snapgene",
            elapsed_s=response.get("elapsed_s"),
            snapgene=response.get("snapgene"),
            dna=dna,
        )


class EstimateOracle:
    """Offline stand-in with the same interface (no ``.dna`` output)."""

    min_anchor = 12

    def evaluate(
        self,
        record: MoleculeRecord,
        primers: Sequence[dict[str, Any]],
        *,
        return_dna: bool = False,
        include_features: bool = False,
    ) -> OracleRun:
        verdicts = {}
        for primer in primers:
            sites = self._sites(record, primer["sequence"].upper())
            verdicts[primer["name"]] = Verdict(
                name=primer["name"],
                sequence=primer["sequence"].upper(),
                imported=bool(sites),
                sites=sites,
            )
        return OracleRun(verdicts=verdicts, tm_standard=ESTIMATE_STANDARD, source="estimate")

    def _sites(self, record: MoleculeRecord, primer: str) -> list[Site]:
        top = record.sequence
        n = len(top)
        circular = record.topology == "circular"
        anchor = min(self.min_anchor, len(primer))
        sites: list[Site] = []
        for strand, target in (("+", top), ("-", revcomp(top))):
            haystack = target + (target[: len(primer)] if circular else "")
            key = primer[-anchor:]
            begin = haystack.find(key)
            while begin != -1 and begin < n:
                three = begin + anchor  # exclusive end of the match in this strand's coordinates
                length = anchor
                while length < len(primer):
                    position = three - length - 1
                    if position < 0 and not circular:
                        break
                    if target[position % n] != primer[-length - 1]:
                        break
                    length += 1
                anneal = primer[-length:]
                up = window(target, three - length - 1, three - length, circular)
                down = window(target, three, three + 1, circular)
                tm = estimate_tm(anneal, up, down)
                if tm is not None and tm >= SNAPGENE_MIN_TM:
                    first = (three - length) % n
                    last = (three - 1) % n + 1
                    if strand == "+":
                        start, end = first, last
                    else:
                        start, end = (n - last) % n, n - first
                    sites.append(Site(start, end, strand, round(tm, 1), anneal))
                begin = haystack.find(key, begin + 1)
        return sites
