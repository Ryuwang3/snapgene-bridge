"""PCR primers flanking a target: primer3 proposes, SnapGene decides."""

from __future__ import annotations

from ..errors import DesignError, InputError
from ..models import MoleculeRecord
from ..seqtools import format_location, interval_length
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

# primer3 conditions chosen to approximate SnapGene's Tm scale (50 mM Na+,
# no Mg2+, SantaLucia parameters and salt correction) so its proposals land
# near the target before SnapGene re-ranks them.
PRIMER3_CONDITIONS = {
    "PRIMER_SALT_MONOVALENT": 50.0,
    "PRIMER_SALT_DIVALENT": 0.0,
    "PRIMER_DNTP_CONC": 0.0,
    "PRIMER_DNA_CONC": 500.0,
    "PRIMER_TM_FORMULA": 1,
    "PRIMER_SALT_CORRECTIONS": 1,
}


def _primer3_candidates(
    record: MoleculeRecord,
    rotated: str,
    offset: int,
    target_start: int,
    target_length: int,
    product_range: tuple[int, int],
    config: DesignConfig,
    count: int,
    prefix: str,
) -> tuple[list[Candidate], list[Candidate], dict[str, tuple[int, int]]]:
    try:
        import primer3
    except ImportError as error:  # pragma: no cover - dependency is declared
        raise InputError("primer3-py is required for PCR design.") from error
    n = len(rotated)
    raw = primer3.bindings.design_primers(
        {
            "SEQUENCE_ID": record.name,
            "SEQUENCE_TEMPLATE": rotated,
            "SEQUENCE_TARGET": [target_start, target_length],
        },
        {
            "PRIMER_TASK": "generic",
            "PRIMER_PICK_LEFT_PRIMER": 1,
            "PRIMER_PICK_RIGHT_PRIMER": 1,
            "PRIMER_PICK_INTERNAL_OLIGO": 0,
            "PRIMER_NUM_RETURN": count,
            "PRIMER_MIN_SIZE": config.min_length,
            "PRIMER_OPT_SIZE": (config.min_length + config.max_length) // 2,
            "PRIMER_MAX_SIZE": config.max_length,
            "PRIMER_MIN_TM": config.target_tm - 6,
            "PRIMER_OPT_TM": config.target_tm,
            "PRIMER_MAX_TM": config.target_tm + 6,
            "PRIMER_PAIR_MAX_DIFF_TM": 6.0,
            "PRIMER_PRODUCT_SIZE_RANGE": [list(product_range)],
            **PRIMER3_CONDITIONS,
        },
    )
    pairs = int(raw.get("PRIMER_PAIR_NUM_RETURNED", 0))
    if pairs == 0:
        raise DesignError(
            "primer3 found no primer pair around the target.",
            hint="Widen --product-size or the primer length range.",
            details={
                "left": raw.get("PRIMER_LEFT_EXPLAIN"),
                "right": raw.get("PRIMER_RIGHT_EXPLAIN"),
                "pair": raw.get("PRIMER_PAIR_EXPLAIN"),
            },
        )
    forward: dict[str, Candidate] = {}
    reverse: dict[str, Candidate] = {}
    rotated_sites: dict[str, tuple[int, int]] = {}
    for index in range(pairs):
        for side, store, letter in (("LEFT", forward, "F"), ("RIGHT", reverse, "R")):
            position, length = raw[f"PRIMER_{side}_{index}"]
            sequence = raw[f"PRIMER_{side}_{index}_SEQUENCE"].upper()
            if sequence in {c.anneal for c in store.values()}:
                continue
            # primer3 reports a right primer by its 5' (rightmost) base
            rotated_start = position if side == "LEFT" else position - length + 1
            strand = "+" if side == "LEFT" else "-"
            name = f"{prefix}_{letter}{len(store) + 1}"
            start, end = site_bounds(rotated_start + offset, length, n)
            store[name] = Candidate(
                name=name,
                role="forward" if side == "LEFT" else "reverse",
                tail="",
                anneal=sequence,
                start=start,
                end=end,
                strand=strand,
                est_tm=estimated_tm(record, rotated_start + offset, length, strand, sequence),
                penalty=float(raw.get(f"PRIMER_{side}_{index}_PENALTY", 0.0)),
            )
            rotated_sites[name] = (rotated_start, rotated_start + length)
    return list(forward.values()), list(reverse.values()), rotated_sites


def design_pcr(
    record: MoleculeRecord,
    start: int,
    end: int,
    *,
    oracle,
    config: DesignConfig = DesignConfig(),
    product_min: int | None = None,
    product_max: int | None = None,
    candidate_pairs: int = 40,
    name_prefix: str = "pcr",
) -> DesignResult:
    """Design a pair whose product contains the whole target interval."""

    n = record.length
    circular = record.topology == "circular"
    target_length = interval_length(start, end, n, circular)
    # Put the target in the middle of a circular template so neither primer
    # has to cross the origin in primer3's linear view.
    offset = ((start + target_length // 2) - n // 2) % n if circular else 0
    rotated = record.sequence[offset:] + record.sequence[:offset]
    target_start = (start - offset) % n
    low = product_min or target_length + 2 * config.min_length + 20
    high = product_max or min(n, target_length + 800)
    if low > high or low > n:
        raise InputError(
            f"Product size range {low}-{high} bp does not fit a {n} bp template.",
            hint="Pass --product-size MIN-MAX explicitly.",
        )
    forward, reverse, rotated_sites = _primer3_candidates(
        record,
        rotated,
        offset,
        target_start,
        target_length,
        (low, high),
        config,
        candidate_pairs,
        name_prefix,
    )
    candidates = forward + reverse
    run = oracle.evaluate(record, [{"name": c.name, "sequence": c.sequence} for c in candidates])
    attach_verdicts(candidates, run, record)
    usable_f, usable_r = screen(forward, config), screen(reverse, config)
    target_end = target_start + target_length
    scored = []
    for f in usable_f:
        f_start, f_end = rotated_sites[f.name]
        if f_end > target_start:
            continue
        for r in usable_r:
            r_start, r_end = rotated_sites[r.name]
            size = r_end - f_start
            if r_start < target_end or not low <= size <= high:
                continue
            difference = abs(f.tm - r.tm)
            if difference > config.max_tm_difference:
                continue
            cost = (
                candidate_cost(f, config) + candidate_cost(r, config) + TM_WEIGHT_PAIR * difference
            )
            scored.append((cost, f, r, f_start, r_end))
    if not scored:
        raise DesignError(
            "No flanking pair met the SnapGene Tm, Tm-difference, and off-target limits.",
            hint="Widen --product-size or --length, or relax --max-dtm / --offtarget-max-tm.",
            details={
                "usable_forward": len(usable_f),
                "usable_reverse": len(usable_r),
                "rejected": rejection_counts(candidates),
            },
        )
    scored.sort(key=lambda item: item[0])
    pairs = []
    for cost, f, r, f_start, r_end in scored[: config.alternatives]:
        pairs.append(
            PairChoice(
                forward=f,
                reverse=r,
                product_start=(f_start + offset) % n,
                product_end=(r_end - 1 + offset) % n + 1,
                amplicon=rotated[f_start:r_end],
                cost=cost,
                checks=secondary_structure(f.sequence, r.sequence, config.target_tm),
            )
        )
    warnings = []
    best = pairs[0]
    for candidate in (best.forward, best.reverse):
        if abs(candidate.tm - config.target_tm) > 2:
            warnings.append(
                f"{candidate.name}: SnapGene Tm {candidate.tm:g} C is more than 2 C from the "
                f"target {config.target_tm:g} C."
            )
    region = {
        "start": start,
        "end": end,
        "location": format_location(start, end, n),
        "target_length": target_length,
        "product_size_range": [low, high],
    }
    return DesignResult("pcr", record, region, pairs, run, candidates, config, warnings)
