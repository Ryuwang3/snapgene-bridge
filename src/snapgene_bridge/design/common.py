"""Shared candidate model, SnapGene verdict matching, and pair selection."""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..models import MoleculeRecord
from ..oracle import OracleRun, Site
from ..seqtools import format_location, gc_fraction, revcomp, window
from ..tm import estimate_tm

TM_WEIGHT_PAIR = 0.5


def site_bounds(start: int, length: int, n: int) -> tuple[int, int]:
    """Normalise an annealing site that may run past the origin."""

    return start % n, (start + length - 1) % n + 1


def estimated_tm(
    record: MoleculeRecord, start: int, length: int, strand: str, anneal: str
) -> float | None:
    """Local estimate with the template bases flanking the site as dangling ends.

    ``start`` is unwrapped (it may be negative or run past the end on a
    circular template).
    """

    top, circular = record.sequence, record.topology == "circular"
    left = window(top, start - 1, start, circular)
    right = window(top, start + length, start + length + 1, circular)
    if strand == "+":
        return estimate_tm(anneal, left, right)
    return estimate_tm(anneal, revcomp(right), revcomp(left))


@dataclass(frozen=True)
class DesignConfig:
    target_tm: float = 60.0
    max_tm_difference: float = 2.0
    min_length: int = 18
    max_length: int = 30
    offtarget_max_tm: float = 45.0
    alternatives: int = 5


@dataclass
class Candidate:
    """One primer option.  ``start``/``end``/``strand`` describe the intended
    annealing site on the template top strand (zero-based, half-open; wraps
    when ``end <= start`` on a circular template)."""

    name: str
    role: str
    tail: str
    anneal: str
    start: int
    end: int
    strand: str
    est_tm: float | None = None
    penalty: float = 0.0
    imported: bool = False
    tm: float | None = None
    main_site: Site | None = None
    off_targets: list[Site] = field(default_factory=list)
    rejection: str | None = None

    @property
    def sequence(self) -> str:
        return self.tail + self.anneal

    def three_prime(self, length: int) -> int:
        return self.end % length if self.strand == "+" else self.start % length

    def to_dict(self, length: int, tm_standard: str) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "sequence": self.sequence,
            "length": len(self.sequence),
            "tail": self.tail,
            "anneal": self.anneal,
            "gc_percent": round(100 * gc_fraction(self.anneal), 1),
            "tm": self.tm,
            "tm_standard": tm_standard,
            "estimated_tm": None if self.est_tm is None else round(self.est_tm, 1),
            "site": self.main_site.to_dict(length) if self.main_site else None,
            "intended_location": format_location(self.start, self.end, length),
            "off_targets": [site.to_dict(length) for site in self.off_targets],
        }


def attach_verdicts(candidates: list[Candidate], run: OracleRun, record: MoleculeRecord) -> None:
    """Find each candidate's intended site among the sites SnapGene reported.

    A site matches when it lies on the intended strand and ends at the
    intended 3' position.  Its 5' edge may differ: SnapGene extends the
    annealed region when tail bases happen to pair with the template.
    """

    n = record.length
    for candidate in candidates:
        verdict = run.verdicts.get(candidate.name)
        candidate.imported = bool(verdict and verdict.imported)
        if not verdict:
            continue
        main = [
            site
            for site in verdict.sites
            if site.strand == candidate.strand and site.three_prime(n) == candidate.three_prime(n)
        ]
        candidate.main_site = main[0] if main else None
        candidate.tm = candidate.main_site.tm if candidate.main_site else None
        candidate.off_targets = [site for site in verdict.sites if site is not candidate.main_site]


def screen(candidates: list[Candidate], config: DesignConfig) -> list[Candidate]:
    """Return usable candidates and record a reason on the others."""

    usable = []
    for candidate in candidates:
        if not candidate.imported:
            candidate.rejection = "no_binding_site"
        elif candidate.main_site is None or candidate.tm is None:
            candidate.rejection = "intended_site_not_found"
        elif any(
            site.tm is not None and site.tm >= config.offtarget_max_tm
            for site in candidate.off_targets
        ):
            candidate.rejection = "off_target"
        else:
            usable.append(candidate)
    return usable


def rejection_counts(candidates: list[Candidate]) -> dict[str, int]:
    return dict(Counter(c.rejection for c in candidates if c.rejection))


def candidate_cost(candidate: Candidate, config: DesignConfig) -> float:
    cost = abs(candidate.tm - config.target_tm)
    cost += 0.01 * len(candidate.anneal)  # shorter is cheaper when Tm ties
    if candidate.anneal[-1:] not in ("G", "C"):
        cost += 0.05  # mild preference for a 3' G/C clamp
    return cost + 0.01 * candidate.penalty


@dataclass
class PairChoice:
    forward: Candidate
    reverse: Candidate
    product_start: int
    product_end: int
    amplicon: str
    cost: float
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, record: MoleculeRecord, tm_standard: str) -> dict[str, Any]:
        n = record.length
        return {
            "forward": self.forward.to_dict(n, tm_standard),
            "reverse": self.reverse.to_dict(n, tm_standard),
            "tm_difference": abs(self.forward.tm - self.reverse.tm),
            "product": {
                "start": self.product_start,
                "end": self.product_end,
                "location": format_location(self.product_start, self.product_end, n),
                "length": len(self.amplicon),
                "sequence": self.amplicon,
            },
            "checks": self.checks,
            "cost": round(self.cost, 3),
        }


def secondary_structure(forward: str, reverse: str, target_tm: float) -> dict[str, Any]:
    """primer3 hairpin and dimer values plus plain-language warnings."""

    try:
        import primer3
    except ImportError:  # pragma: no cover - dependency is declared
        return {}
    conditions = dict(mv_conc=50.0, dv_conc=0.0, dntp_conc=0.0, dna_conc=250.0)
    values = {
        "forward_hairpin_tm": primer3.calc_hairpin(forward, **conditions).tm,
        "reverse_hairpin_tm": primer3.calc_hairpin(reverse, **conditions).tm,
        "forward_self_dimer_dg": primer3.calc_homodimer(forward, **conditions).dg / 1000,
        "reverse_self_dimer_dg": primer3.calc_homodimer(reverse, **conditions).dg / 1000,
        "pair_dimer_dg": primer3.calc_heterodimer(forward, reverse, **conditions).dg / 1000,
    }
    warnings = []
    for key in ("forward_hairpin_tm", "reverse_hairpin_tm"):
        if values[key] > target_tm - 5:
            warnings.append(f"{key.split('_')[0]} primer hairpin melts at {values[key]:.0f} C")
    for key in ("forward_self_dimer_dg", "reverse_self_dimer_dg", "pair_dimer_dg"):
        if values[key] < -12:
            warnings.append(f"strong dimer ({key}: {values[key]:.1f} kcal/mol)")
    rounded = {key: round(value, 1) for key, value in values.items()}
    return {**rounded, "units": "C and kcal/mol", "warnings": warnings}


@dataclass
class DesignResult:
    mode: str
    record: MoleculeRecord
    region: dict[str, Any]
    pairs: list[PairChoice]
    run: OracleRun
    candidates: list[Candidate]
    config: DesignConfig
    warnings: list[str] = field(default_factory=list)

    @property
    def best(self) -> PairChoice:
        return self.pairs[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "molecule": {
                "name": self.record.name,
                "length": self.record.length,
                "topology": self.record.topology,
            },
            "region": self.region,
            "tm_standard": self.run.tm_standard,
            "oracle": self.run.meta(),
            "settings": {
                "target_tm": self.config.target_tm,
                "max_tm_difference": self.config.max_tm_difference,
                "primer_length": [self.config.min_length, self.config.max_length],
                "offtarget_max_tm": self.config.offtarget_max_tm,
            },
            "best": self.best.to_dict(self.record, self.run.tm_standard),
            "alternatives": [
                pair.to_dict(self.record, self.run.tm_standard) for pair in self.pairs[1:]
            ],
            "candidates": {
                "evaluated": len(self.candidates),
                "usable": sum(c.rejection is None for c in self.candidates),
                "rejected": rejection_counts(self.candidates),
            },
            "warnings": self.warnings,
        }


def order_sheet(rows: list[dict[str, Any]]) -> str:
    """Tab-separated oligo order sheet (name, 5'->3' sequence, length, Tm, notes)."""

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(
        ["Name", "Sequence (5'->3')", "Length", "Anneal Tm (C)", "Tm standard", "Notes"]
    )
    for row in rows:
        writer.writerow(
            [
                row["name"],
                row["sequence"],
                len(row["sequence"]),
                "" if row.get("tm") is None else f"{row['tm']:g}",
                row.get("tm_standard", ""),
                row.get("notes", ""),
            ]
        )
    return buffer.getvalue()


def pair_order_rows(pair: PairChoice, tm_standard: str) -> list[dict[str, Any]]:
    rows = []
    for candidate in (pair.forward, pair.reverse):
        if candidate.main_site and len(candidate.main_site.annealed) != len(candidate.anneal):
            # SnapGene paired some tail bases with the template as well
            notes = f"anneal {len(candidate.main_site.annealed)} nt per SnapGene"
        else:
            notes = f"anneal {len(candidate.anneal)} nt"
        if candidate.tail:
            notes += f"; 5' tail {candidate.tail}"
        rows.append(
            {
                "name": candidate.name,
                "sequence": candidate.sequence,
                "tm": candidate.tm,
                "tm_standard": tm_standard,
                "notes": notes,
            }
        )
    return rows
