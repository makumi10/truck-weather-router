"""End-to-end planner tests with routing/geocoding/weather mocked."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from routing import geo, geocode, osrm, planner, weather

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
MIDNIGHT = int(datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp())


def make_route(lat, duration_s, n=200):
    coords = np.column_stack([np.full(n, lat), np.linspace(-90, -80, n)])
    cum = geo.cumulative_miles(coords)
    return osrm.Route(coords=coords, cum=cum, distance_mi=float(cum[-1]), duration_s=duration_s)


@pytest.fixture
def setup(monkeypatch):
    """Route A (lat 30, fastest) and B (lat 31.5, slower). wind per latitude band is configurable."""
    cfg = {"wind_a": 5.0, "wind_b": 5.0, "rain": 0.0, "snow": 0.0}
    monkeypatch.setattr(geocode, "geocode", lambda q: {"query": q, "name": q, "lat": 30.0, "lng": -90.0})
    monkeypatch.setattr(osrm, "get_routes", lambda o, d, want=3: [make_route(30.0, 36000), make_route(31.5, 40000)])

    def fake_fetch(coords):
        out = {}
        for lat, lng in coords:
            wind = cfg["wind_a"] if lat < 30.75 else cfg["wind_b"]
            out[weather.key(lat, lng)] = weather.Series(
                MIDNIGHT, [wind] * 96, [cfg["rain"]] * 96, [cfg["snow"]] * 96)
        return out

    monkeypatch.setattr(weather, "fetch_series", fake_fetch)
    return cfg


def run(load=20_000, dep=NOW + timedelta(hours=1), spacing="auto"):
    return planner.plan_trip("A", "B", dep, load, spacing, now=NOW)


def test_calm_weather_recommends_fastest(setup):
    res = run()
    assert res["recommendation"]["label"] == "A"
    assert [r["rank"] for r in res["routes"]] == [1, 2]


def test_avoids_severe_route_even_if_faster(setup):
    setup["wind_a"] = 40.0                       # 35-44 mph + >40,000 lb => Severe on route A
    res = run(load=45_000)
    assert res["recommendation"]["label"] == "B"
    a = next(r for r in res["routes"] if r["label"] == "A")
    assert a["summary"]["miles_by_level"]["severe"] > 0
    assert "Severe" in res["recommendation"]["reason"] or "No Travel" in res["recommendation"]["reason"]


def test_same_wind_light_load_is_only_high(setup):
    setup["wind_a"] = 40.0
    res = run(load=20_000)
    a = next(r for r in res["routes"] if r["label"] == "A")
    assert a["summary"]["miles_by_level"]["severe"] == 0
    assert a["summary"]["miles_by_level"]["high"] > 0
    assert res["recommendation"]["label"] == "B"  # fewer High miles wins


def test_wind_55_is_no_travel_for_any_load(setup):
    setup["wind_a"] = 56.0
    res = run(load=0)
    a = next(r for r in res["routes"] if r["label"] == "A")
    assert a["summary"]["worst_level"] == "no_travel"
    assert res["recommendation"]["label"] == "B"


def test_checkpoint_etas_increase_and_segments_sum(setup):
    res = run()
    for r in res["routes"]:
        etas = [c["eta"] for c in r["checkpoints"]]
        assert etas == sorted(etas)
        assert abs(sum(c["segment_miles"] for c in r["checkpoints"]) - r["summary"]["distance_mi"]) < 1.0
        assert r["checkpoints"][0]["mile"] == 0
        assert abs(sum(r["summary"]["miles_by_level"].values()) - r["summary"]["distance_mi"]) < 1.0


def test_spacing_options(setup):
    a10 = run(spacing="10")["routes"][0]["checkpoints"]
    a50 = run(spacing="50")["routes"][0]["checkpoints"]
    assert len(a10) > len(a50)
    assert planner.choose_spacing("auto", 100) == 10
    assert planner.choose_spacing("auto", 300) == 25
    assert planner.choose_spacing("auto", 900) == 50


def test_far_future_departure_is_flagged(setup):
    res = run(dep=NOW + timedelta(days=10))
    assert all(r["summary"]["forecast_clamped"] for r in res["routes"])
    assert any("forecast" in n for n in res["notes"])


def test_heatmap_has_49_hourly_levels(setup):
    hm = run()["heatmap"]
    assert hm["hours"] == 48 and len(hm["points"]) > 5
    assert all(len(p[2]) == 49 for p in hm["points"])


def test_eta_uses_departure_time(setup):
    early = run(dep=NOW + timedelta(hours=1))["routes"][0]["checkpoints"][-1]["eta"]
    later = run(dep=NOW + timedelta(hours=3))["routes"][0]["checkpoints"][-1]["eta"]
    assert later > early
