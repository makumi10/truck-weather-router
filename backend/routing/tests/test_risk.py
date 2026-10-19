import pytest
from routing.risk import (wind_level, rain_level, snow_level, classify,
                          LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL)


@pytest.mark.parametrize("v,exp", [(0, LOW), (24.99, LOW), (25, MODERATE), (34.99, MODERATE),
    (35, HIGH), (44.99, HIGH), (45, SEVERE), (54.99, SEVERE), (55, NO_TRAVEL), (80, NO_TRAVEL)])
def test_wind(v, exp): assert wind_level(v) == exp


@pytest.mark.parametrize("v,exp", [(0.099, LOW), (0.10, MODERATE), (0.25, HIGH), (0.499, HIGH),
    (0.50, SEVERE), (1.00, SEVERE), (1.0001, NO_TRAVEL)])
def test_rain(v, exp): assert rain_level(v) == exp


@pytest.mark.parametrize("v,exp", [(0.49, LOW), (0.5, MODERATE), (1.0, HIGH), (2.0, SEVERE),
    (3.0, SEVERE), (3.01, NO_TRAVEL)])
def test_snow(v, exp): assert snow_level(v) == exp


def test_wind_55_no_travel_any_load():
    assert classify(55, 0, 0, 0).level == NO_TRAVEL


def test_wind_45_54_heavy_load_no_travel():
    assert classify(45, 0, 0, 30_001).level == NO_TRAVEL
    assert classify(54, 0, 0, 30_001).level == NO_TRAVEL


def test_wind_45_54_at_30000_stays_severe():  # rule is ">30,000"
    assert classify(50, 0, 0, 30_000).level == SEVERE


def test_wind_35_44_heavy_load_severe():
    assert classify(35, 0, 0, 40_001).level == SEVERE
    assert classify(44, 0, 0, 40_001).level == SEVERE


def test_wind_35_44_at_40000_stays_high():
    assert classify(40, 0, 0, 40_000).level == HIGH


def test_light_load_no_escalation():
    assert classify(40, 0, 0, 10_000).level == HIGH


def test_worst_of_all_conditions_wins():
    assert classify(10, 0.6, 0.2, 5_000).level == SEVERE
    assert classify(30, 0.0, 3.5, 5_000).level == NO_TRAVEL


def test_escalation_never_downgrades():
    assert classify(40, 1.5, 0, 50_000).level == NO_TRAVEL
