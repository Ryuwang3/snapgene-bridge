import pytest

from snapgene_bridge.design import DesignConfig, design_clone, design_pcr
from snapgene_bridge.design.common import Candidate, attach_verdicts, order_sheet, pair_order_rows
from snapgene_bridge.errors import DesignError
from snapgene_bridge.io import read_record
from snapgene_bridge.models import MoleculeRecord
from snapgene_bridge.oracle import EstimateOracle, OracleRun, Site, Verdict


@pytest.fixture
def puc19(data_dir):
    return read_record(data_dir / "pUC19_L09137.gb")


def test_clone_on_minus_strand_insert_anchors_both_ends(puc19):
    # bla (AmpR) CDS is complement(1626..2486) in L09137
    result = design_clone(
        puc19,
        1625,
        2486,
        oracle=EstimateOracle(),
        insert_strand="-",
        tail_f="GCGCTAGC",
        tail_r="GCCTCGAG",
        name_prefix="bla",
    )
    best = result.best
    assert best.forward.sequence.startswith("GCGCTAGCATGAGTATTCAACATTTC")  # starts at ATG
    assert best.reverse.sequence.startswith("GCCTCGAGTTACCAATGCTTAATCAG")  # ends at TAA
    assert (best.forward.strand, best.forward.end) == ("-", 2486)
    assert (best.reverse.strand, best.reverse.start) == ("+", 1625)
    assert len(best.amplicon) == 861 + 16
    assert abs(best.forward.tm - best.reverse.tm) <= 2


def test_main_site_may_extend_into_tail_bases():
    """SnapGene counts tail bases that pair by chance; the 3' end still identifies the site."""

    record = MoleculeRecord(name="t", sequence="A" * 50 + "GATTACAGATTACAGGCCTT" + "C" * 50)
    candidate = Candidate("R", "reverse", "GG", "AAGGCCTGTAATCTGTAATC", 50, 70, "-")
    run = OracleRun(
        verdicts={
            "R": Verdict(
                "R",
                candidate.sequence,
                True,
                [
                    Site(50, 72, "-", 61.0, "x" * 22),  # extended 2 nt past the intended 5' edge
                    Site(5, 15, "+", 20.0, "y" * 10),
                ],
            )
        },
        tm_standard="snapgene-8.0.0",
        source="snapgene",
    )
    attach_verdicts([candidate], run, record)
    assert candidate.tm == 61.0
    assert [s.start for s in candidate.off_targets] == [5]


def test_offtarget_limit_rejects_candidates(puc19):
    strict = DesignConfig(min_length=16, max_length=36, offtarget_max_tm=-1)
    with pytest.raises(DesignError) as info:
        design_clone(puc19, 1625, 2486, oracle=_OffTargetOracle(), insert_strand="-", config=strict)
    assert info.value.details["rejected"]["off_target"] > 0


class _OffTargetOracle(EstimateOracle):
    def evaluate(self, record, primers, **kwargs):
        run = super().evaluate(record, primers, **kwargs)
        for verdict in run.verdicts.values():
            verdict.sites.append(Site(0, 10, "+", 30.0, "N" * 10))
        return run


def test_pcr_product_contains_target_and_wraps_origin(puc19):
    result = design_pcr(puc19, 1625, 2486, oracle=EstimateOracle(), name_prefix="amp")
    best = result.best
    assert best.forward.strand == "+" and best.reverse.strand == "-"
    product = best.amplicon
    target = puc19.sequence[1625:2486]
    assert target in product
    low, high = result.region["product_size_range"]
    assert low <= len(product) <= high


def test_order_sheet_lists_both_primers(puc19):
    result = design_clone(puc19, 1625, 2486, oracle=EstimateOracle(), insert_strand="-")
    sheet = order_sheet(pair_order_rows(result.best, result.run.tm_standard))
    lines = sheet.strip().splitlines()
    assert lines[0].startswith("Name\tSequence")
    assert len(lines) == 3 and "estimate:nn" in lines[1]
