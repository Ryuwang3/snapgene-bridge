from snapgene_bridge.oracle import Site, Verdict
from snapgene_bridge.selftest import SUITES, check_suite, load_suite


def _perfect_verdicts(suite):
    verdicts = {}
    for primer in suite["primers"]:
        expected = suite["expected"][primer["name"]]
        if "sites" in expected:
            sites = [
                Site(x["start"], x["end"], x["strand"], x["tm"], "") for x in expected["sites"]
            ]
        elif expected["imported"]:
            main = expected["main"]
            sites = [Site(main["start"], main["end"], main["strand"], main["tm"], "")]
            sites += [Site(o[0], o[1], o[2], o[3], "") for o in expected["other_sites"]]
        else:
            sites = []
        verdicts[primer["name"]] = Verdict(
            primer["name"], primer["sequence"], expected["imported"], sites
        )
    return verdicts


def test_suites_load_and_accept_their_own_expectations():
    for name in SUITES:
        suite = load_suite(name)
        assert suite["snapgene_version"] == "8.0.0"
        assert check_suite(name, suite, _perfect_verdicts(suite)) == []


def test_suite_reports_tm_drift():
    suite = load_suite("regression6")
    verdicts = _perfect_verdicts(suite)
    verdicts["P1_fwd_perfect"].sites[0].tm = 61.0
    problems = check_suite("regression6", suite, verdicts)
    assert len(problems) == 1 and problems[0].startswith("P1_fwd_perfect")
