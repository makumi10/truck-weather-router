from routing import weather


def test_parse_payload_handles_none_and_sums_rain_showers():
    data = {"hourly": {"time": [1000, 4600], "wind_speed_10m": [10, None],
                       "rain": [0.1, 0.0], "showers": [0.05, None], "snowfall": [None, 0.4]}}
    s = weather.parse_payload(data)[0]
    assert s.wind == [10, 0.0]
    assert abs(s.rain[0] - 0.15) < 1e-9 and s.rain[1] == 0.0
    assert s.snow == [0.0, 0.4]


def test_parse_payload_multi_location_list():
    one = {"hourly": {"time": [0], "wind_speed_10m": [1], "rain": [0], "showers": [0], "snowfall": [0]}}
    assert len(weather.parse_payload([one, one])) == 2


def _series():
    return weather.Series(t0=0, wind=[0, 10, 20, 30], rain=[0] * 4, snow=[0] * 4)


def test_nearest_hour_selection():
    assert weather.sample(_series(), 3600 * 1 + 1200)["wind"] == 10      # 1.33h -> hour 1
    assert weather.sample(_series(), 3600 * 1 + 2400)["wind"] == 20      # 1.67h -> hour 2


def test_clamps_and_flags_outside_forecast():
    late = weather.sample(_series(), 3600 * 50)
    early = weather.sample(_series(), -3600 * 5)
    assert late["clamped"] and late["wind"] == 30
    assert early["clamped"] and early["wind"] == 0
    assert not weather.sample(_series(), 3600 * 3)["clamped"]


# ---- resilience ----
import pytest
import requests
from django.core.cache import cache


class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._p, self.text = status, payload, str(payload)

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def payload_for(n):
    return [{"hourly": {"time": [0, 3600], "wind_speed_10m": [10, 12], "rain": [0, 0],
                        "showers": [0, 0], "snowfall": [0, 0]}} for _ in range(n)]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    cache.clear()
    monkeypatch.setattr(weather.time, "sleep", lambda s: None)


COORDS = [(30 + i * 0.1, -90.0) for i in range(5)]


def test_retries_then_succeeds(monkeypatch):
    calls = []

    def fake_get(url, params=None, **kw):
        calls.append(1)
        n = len(params["latitude"].split(","))
        return FakeResp(429, {"error": True}) if len(calls) < 3 else FakeResp(200, payload_for(n))

    monkeypatch.setattr(weather.requests, "get", fake_get)
    out = weather.fetch_series(COORDS)
    assert len(out) == 5 and len(calls) == 3


def test_stale_cache_used_when_live_fails(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", lambda url, params=None, **kw: FakeResp(200, payload_for(5)))
    weather.fetch_series(COORDS)                       # primes fresh + stale caches
    cache.delete_many([weather._ckey(weather.key(*c)) for c in COORDS])  # fresh copies expire
    monkeypatch.setattr(weather.requests, "get", lambda url, params=None, **kw: FakeResp(503, {}))
    out = weather.fetch_series(COORDS)
    assert len(out) == 5 and all(s.stale for s in out.values())


def test_total_failure_without_stale_returns_empty(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", lambda url, params=None, **kw: FakeResp(500, {}))
    assert weather.fetch_series(COORDS) == {}


def test_successful_batches_are_cached_even_if_another_fails(monkeypatch):
    coords = [(30 + i * 0.1, -90.0) for i in range(60)]      # batches of 50 + 10

    def fake_get(url, params=None, **kw):
        n = len(params["latitude"].split(","))
        return FakeResp(200, payload_for(n)) if n == 50 else FakeResp(500, {})

    monkeypatch.setattr(weather.requests, "get", fake_get)
    out = weather.fetch_series(coords)
    assert len(out) == 50
    cached = cache.get_many([weather._ckey(k) for k in out])
    assert len(cached) == 50                                  # a retry only needs the missing 10
