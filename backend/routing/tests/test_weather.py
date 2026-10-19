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
