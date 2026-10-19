import numpy as np
from routing import geo


def test_haversine_nyc_la():
    d = float(geo.haversine_mi(40.7128, -74.0060, 34.0522, -118.2437))
    assert 2400 < d < 2490


def test_sample_miles_includes_start_and_end():
    m = geo.sample_miles(120, 25)
    assert m[0] == 0 and m[-1] == 120 and m[1] == 25


def test_sample_miles_avoids_tiny_last_hop():
    m = geo.sample_miles(101, 25)   # 100 would leave a 1-mile hop
    assert m[-2] == 75 and m[-1] == 101


def test_sample_miles_short_trip():
    assert geo.sample_miles(4, 10) == [0.0, 4.0]


def test_ownership_sums_to_length():
    miles = geo.sample_miles(237.5, 25)
    assert abs(sum(geo.ownership(miles)) - 237.5) < 1e-9


def test_point_at_mile_midpoint():
    coords = np.array([[0.0, 0.0], [0.0, 1.0]])
    cum = geo.cumulative_miles(coords)
    lat, lng, _ = geo.point_at_mile(coords, cum, cum[-1] / 2)
    assert abs(lat) < 1e-9 and abs(lng - 0.5) < 1e-6


def test_offset_point_distance():
    lat, lng = geo.offset_point(40, -100, 90, 10)
    assert abs(float(geo.haversine_mi(40, -100, lat, lng)) - 10) < 0.01


def test_fraction_far():
    a = np.array([[0, 0], [0, 1]], float)
    assert geo.fraction_far(a, a, 1.0) == 0.0
    assert geo.fraction_far(a, a + [5, 0], 1.0) == 1.0
