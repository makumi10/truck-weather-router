from django.core.cache import cache
from routing import osrm


def _raw():
    coords = [[-90 + i * 0.1, 30.0] for i in range(100)]
    return {"geometry": {"coordinates": coords}, "distance": 900_000, "duration": 36_000}


def test_get_routes_cached_per_trip(monkeypatch):
    cache.clear()
    calls = []

    def fake_request(points, alternatives):
        calls.append(1)
        return [_raw()]

    monkeypatch.setattr(osrm, "_request", fake_request)
    o, d = {"lat": 30.0, "lng": -90.0}, {"lat": 30.0, "lng": -80.0}
    first = osrm.get_routes(o, d)
    n = len(calls)
    second = osrm.get_routes(o, d)
    assert n >= 1 and len(calls) == n          # second call served from cache
    assert len(first) == len(second) == 1       # identical routes are de-duplicated
