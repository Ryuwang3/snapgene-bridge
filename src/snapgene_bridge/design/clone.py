"""Cloning primers: fixed ends on an insert, optional 5' tails, lengths chosen by SnapGene Tm."""

from __future__ import annotations

from ..errors import DesignError, InputError
from ..models import MoleculeRecord
from ..seqtools import format_location, revcomp, slice_interval
from .common import (
    TM_WEIGHT_PAIR,
    Candidate,
    DesignConfig,
    DesignResult,
    PairChoice,
    attach_verdicts,
    candidate_cost,
    estimated_tm,
    rejection_counts,
    screen,
    secondary_structure,
    site_bounds,
)

CLONE_DEFAULTS = DesignConfig(min_length=16, max_length=36)


def _candidates(
    record: MoleculeRecord,
    start: int,
    end: int,
    insert_strand: str,
    tail_f: str,
    tail_r: str,
    config: DesignConfig,
    prefix: str,
) -> tuple[list[Candidate], list[Candidate], str]:
    n = record.length
    circular = record.topology == "circular"
    top_region = slice_interval(record.sequence, start, end, circular)
    insert = top_region if insert_strand == "+" else revcomp(top_region)
    if len(insert) < config.min_length:
        raise InputError(
            f"The insert is {len(insert)} bp, shorter than the minimum primer length "
            f"{config.min_length}."
        )
    # unwrapped coordinate of the region end, so arithmetic stays monotonic
    stop = start + len(insert)
    forward, reverse = [], []
    for length in range(config.min_length, min(config.max_length, len(insert)) + 1):
        f_anneal = insert[:length]
        r_anneal = revcomp(insert[-length:])
        if insert_strand == "+":
            f_site, f_strand = start, "+"
            r_site, r_strand = stop - length, "-"
        else:
            f_site, f_strand = stop - length, "-"
            r_site, r_strand = start, "+"
        for role, items, anneal, tail, site, strand, letter in (
            ("forward", forward, f_anneal, tail_f, f_site, f_strand, "F"),
            ("reverse", reverse, r_anneal, tail_r, r_site, r_strand, "R"),
        ):
            site_start, site_end = site_bounds(site, length, n)
            items.append(
                Candidate(
                    name=f"{prefix}_{letter}{length}",
                    role=role,
                    tail=tail,
                    anneal=anneal,
                    start=site_start,
                    end=site_end,
                    strand=strand,
                    est_tm=estimated_tm(record, site, length, strand, anneal),
                )
            )
    return forward, reverse, insert


def design_clone(
    record: MoleculeRecord,
    start: int,
    end: int,
    *,
    oracle,
    insert_strand: str = "+",
    tail_f: str = "",
    tail_r: str = "",
    config: DesignConfig = CLONE_DEFAULTS,
    name_prefix: str = "insert",
) -> DesignResult:
    """Design primers whose 3' parts start exactly at the insert ends.

    Every length between ``config.min_length`` and ``config.max_length`` is
    sent to the oracle in one batch; the pair closest to the target Tm wins.
    """

    if insert_strand not in ("+", "-"):
        raise InputError("insert_strand must be '+' or '-'.")
    tail_f, tail_r = tail_f.upper(), tail_r.upper()
    forward, reverse, insert = _candidates(
        record, start, end, insert_strand, tail_f, tail_r, config, name_prefix
    )
    candidates = forward + reverse
    run = oracle.evaluate(record, [{"name": c.name, "sequence": c.sequence} for c in candidates])
    attach_verdicts(candidates, run, record)
    usable_f, usable_r = screen(forward, config), screen(reverse, config)
    scored = []
    for f in usable_f:
        for r in usable_r:
            difference = abs(f.tm - r.tm)
            if difference > config.max_tm_difference:
                continue
            cost = (
                candidate_cost(f, config) + candidate_cost(r, config) + TM_WEIGHT_PAIR * difference
            )
            scored.append((cost, f, r))
    if not scored:
        best_f = max((c.tm for c in usable_f), default=None)
        best_r = max((c.tm for c in usable_r), default=None)
        raise DesignError(
            "No forward/reverse pair met the Tm-difference and off-target limits.",
            hint="Widen --length, relax --max-dtm or --offtarget-max-tm, or move the region.",
            details={
                "usable_forward": len(usable_f),
                "usable_reverse": len(usable_r),
                "highest_forward_tm": best_f,
                "highest_reverse_tm": best_r,
                "rejected": rejection_counts(candidates),
            },
        )
    scored.sort(key=lambda item: item[0])
    amplicon = tail_f + insert + revcomp(tail_r)
    pairs = []
    for cost, f, r in scored[: config.alternatives]:
        pairs.append(
            PairChoice(
                forward=f,
                reverse=r,
                product_start=start,
                product_end=end,
                amplicon=amplicon,
                cost=cost,
                checks=secondary_structure(f.sequence, r.sequence, config.target_tm),
            )
        )
    warnings = []
    best = pairs[0]
    for candidate in (best.forward, best.reverse):
        if abs(candidate.tm - config.target_tm) > 2:
            warnings.append(
                f"{candidate.name}: closest achievable Tm is {candidate.tm:g} C "
                f"(target {config.target_tm:g} C)."
            )
    if tail_f or tail_r:
        warnings.append("Reported Tm covers the annealing part only; 5' tails are excluded.")
    region = {
        "start": start,
        "end": end,
        "location": format_location(start, end, record.length),
        "insert_strand": insert_strand,
        "insert_length": len(insert),
        "tail_forward": tail_f,
        "tail_reverse": tail_r,
    }
    return DesignResult("clone", record, region, pairs, run, candidates, config, warnings)
