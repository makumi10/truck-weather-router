"""Open-Meteo client (free, no key).

One request can carry many coordinates, so we batch and run batches in parallel.
Each location's hourly series (today 00:00 UTC + 4 days) is cached for 30 minutes
and shared between route checkpoints and the heatmap grid.

Units are requested directly: wind mph, precipitation/snowfall inches
(hourly values are the amount over the preceding hour == in/hr).
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import PlanningError

log = logging.getLogger(__name__)
BATCH_SIZE = 80
FORECAST_DAYS = 4


@dataclass
class Series:
    t0: int            # unix seconds of first hour (UTC)
    wind: list         # mph
    rain: list         # in/hr (rain + showers)
    snow: list         # in/hr

    @property
    def hours(self) -> int:
        return len(self.wind)


def key(lat: float, lng: float) -> tuple:
    return (round(lat, 2), round(lng, 2))


def _ckey(k) -> str:
    return f"om:{k[0]:.2f}:{k[1]:.2f}"


def parse_payload(data) -> list:
    """Open-Meteo returns a dict for one location, a list for many."""
    if isinstance(data, dict):
        data = [data]
    out = []
    for loc in data:
        h = loc["hourly"]
        n = len(h["time"])
        z = lambda name: [(v or 0.0) for v in h.get(name, [0.0] * n)]
        rain = [a + b for a, b in zip(z("rain"), z("showers"))]
        out.append(Series(t0=int(h["time"][0]), wind=z("wind_speed_10m"), rain=rain, snow=z("snowfall")))
    return out


def _fetch_batch(keys: list) -> list:
    params = {
        "latitude": ",".join(f"{k[0]:.2f}" for k in keys),
        "longitude": ",".join(f"{k[1]:.2f}" for k in keys),
        "hourly": "wind_speed_10m,rain,showers,snowfall",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": FORECAST_DAYS,
    }
    last = None
    for _ in range(2):
        try:
            resp = requests.get(settings.OPEN_METEO_URL, params=params,
                                headers={"User-Agent": settings.HTTP_USER_AGENT}, timeout=40)
            resp.raise_for_status()
            series = parse_payload(resp.json())
            if len(series) != len(keys):
                raise ValueError("unexpected number of locations in weather response")
            return series
        except (requests.RequestException, ValueError, KeyError) as exc:
            last = exc
            log.warning("Open-Meteo batch failed: %s", exc)
    raise PlanningError("The weather service is unavailable. Try again shortly.", 502) from last


def fetch_series(coords) -> dict:
    """coords: iterable of (lat, lng). Returns {key(lat,lng): Series}."""
    keys = list(dict.fromkeys(key(lat, lng) for lat, lng in coords))
    found = cache.get_many([_ckey(k) for k in keys])
    result = {k: found[_ckey(k)] for k in keys if _ckey(k) in found}
    missing = [k for k in keys if k not in result]
    if missing:
        batches = [missing[i:i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            fetched = list(pool.map(_fetch_batch, batches))
        to_cache = {}
        for batch, series in zip(batches, fetched):
            for k, s in zip(batch, series):
                result[k] = s
                to_cache[_ckey(k)] = s
        cache.set_many(to_cache, settings.WEATHER_CACHE_SECONDS)
    return result


def hour_index(series: Series, epoch: float):
    """(index of nearest hour, clamped?) -- clamped when the time is outside the forecast."""
    idx = round((epoch - series.t0) / 3600.0)
    clamped = idx < 0 or idx > series.hours - 1
    return min(max(idx, 0), series.hours - 1), clamped


def sample(series: Series, epoch: float) -> dict:
    idx, clamped = hour_index(series, epoch)
    return {
        "wind": series.wind[idx], "rain": series.rain[idx], "snow": series.snow[idx],
        "clamped": clamped, "hour_epoch": series.t0 + idx * 3600,
    }
