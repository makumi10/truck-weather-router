from routing.scoring import Checkpoint as C, score_route, rank_routes, explain
from routing.risk import LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL


def mk(rid, dur, levels, seg=10):
    cps = [C(i * seg, lv, seg) for i, lv in enumerate(levels)]
    return score_route(rid, dur, seg * len(levels), cps)


def test_miles_attribution_and_avg():
    r = mk("a", 100, [LOW, HIGH, SEVERE])
    assert r.miles_by_level["high"] == 10 and r.miles_by_level["severe"] == 10
    assert r.avg_risk == (0 + 2 + 3) / 3


def test_fewest_severe_beats_faster_route():
    fast = mk("fast", 1000, [LOW, SEVERE, LOW])
    slow = mk("slow", 5000, [HIGH, HIGH, HIGH])
    assert rank_routes([fast, slow])[0].route_id == "slow"


def test_high_miles_second_priority():
    a = mk("a", 1000, [HIGH, HIGH, LOW])
    b = mk("b", 2000, [HIGH, LOW, LOW])
    assert rank_routes([a, b])[0].route_id == "b"


def test_avg_risk_third_priority():
    a = mk("a", 2000, [MODERATE, MODERATE, LOW])
    b = mk("b", 1000, [LOW, LOW, LOW])
    assert rank_routes([a, b])[0].route_id == "b"


def test_duration_last_tiebreak():
    a = mk("a", 3000, [LOW, LOW]); b = mk("b", 2000, [LOW, LOW])
    assert rank_routes([a, b])[0].route_id == "b"


def test_no_travel_is_worst():
    a = mk("a", 100, [NO_TRAVEL, LOW]); b = mk("b", 900, [SEVERE, SEVERE])
    assert rank_routes([a, b])[0].route_id == "b"


def test_explain_mentions_deciding_factor():
    best = mk("b", 2, [LOW, LOW]); other = mk("a", 1, [SEVERE, LOW])
    assert "Severe" in explain(best, [other])
