"""Fast local Tm estimate used to prune candidates before asking SnapGene.

Nearest-neighbour thermodynamics (Allawi & SantaLucia parameters with
Bommarito dangling ends) at 50 mM Na+, no Mg2+, and an effective strand
concentration of 125 nM.  Against 2162 SnapGene 8.0.0 values on perfect-match
sites this variant had a mean absolute error of 0.51 C, matched SnapGene's
integer exactly 61 % of the time, and was off by at most 2.7 C.  It is an
estimate and is always labelled ``estimate:nn`` in output.
"""

from __future__ import annotations

from .seqtools import complement

ESTIMATE_STANDARD = "estimate:nn"
_ACGT = frozenset("ACGT")


def estimate_tm(anneal: str, upstream: str = "", downstream: str = "") -> float | None:
    """Estimate the Tm of ``anneal`` paired to its template.

    ``upstream`` and ``downstream`` are the template-matching bases just 5'
    and 3' of the annealed region, in primer orientation.  Only the base next
    to each duplex end is used (as dangling ends).  Returns ``None`` when the
    sequence has non-ACGT symbols or Biopython is unavailable.
    """

    anneal = anneal.upper()
    if len(anneal) < 2 or set(anneal) - _ACGT:
        return None
    try:
        from Bio.SeqUtils import MeltingTemp as mt
    except ImportError:  # pragma: no cover - dependency is declared
        return None
    up = upstream[-1:].upper() if upstream and upstream[-1].upper() in _ACGT else ""
    down = downstream[:1].upper() if downstream and downstream[0].upper() in _ACGT else ""
    options = dict(nn_table=mt.DNA_NN3, dnac1=250, dnac2=250, saltcorr=5, Na=50)
    try:
        if up or down:
            return mt.Tm_NN(
                anneal,
                c_seq=complement(up + anneal + down),
                shift=len(up),
                de_table=mt.DNA_DE1,
                **options,
            )
        return mt.Tm_NN(anneal, **options)
    except (KeyError, ValueError, ZeroDivisionError):
        return None
