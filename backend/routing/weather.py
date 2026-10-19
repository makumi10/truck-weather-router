"""Open-Meteo client (free, no key), built to survive a flaky or rate-limited upstream.

* Locations are batched (50 per request) and fetched with modest parallelism.
* Each batch is retried with exponential backoff (429 / 5xx / timeouts).
* Every batch that succeeds is cached immediately (30 min fresh, 12 h "stale"), so a retried
  plan only re-fetches what failed.
* If a batch still fails, the last known forecast for those locations (stale copy) is used.
  Anything left over is returned as missing and the planner decides how to degrade.

Units are requested directly: wind mph, precipitation/snowfall inches
(hourly values are the amount over the preceding hour == in/hr).
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)
BATCH_SIZE = 50
MAX_WORKERS = 3
ATTEMPTS = 3
FORECAST_DAYS = 3


@dataclass
class Series:
    t0: int            # unix seconds of first hour (UTC)
    wind: list         # mph
    rain: list         # in/hr (rain + showers)
    snow: list         # in/hr
    stale: bool = False  # True when served from the stale cache after a failed refresh

    @property
    def hours(self) -> int:
        return len(self.wind)


def key(lat: float, lng: float) -> tuple:
    return (round(lat, 2), round(lng, 2))


def _ckey(k) -> str:
    return f"om:{k[0]:.2f}:{k[1]:.2f}"


def _skey(k) -> str:
    return f"om-stale:{k[0]:.2f}:{k[1]:.2f}"


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


def _fetch_batch(keys: list):
    """Returns a list of Series, or None if every attempt failed."""
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
    for attempt in range(ATTEMPTS):
        try:
            resp = requests.get(settings.OPEN_METEO_URL, params=params,
                                headers={"User-Agent": settings.HTTP_USER_AGENT}, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            series = parse_payload(resp.json())
            if len(series) != len(keys):
                raise ValueError("unexpected number of locations in weather response")
            return series
        except (requests.RequestException, ValueError, KeyError) as exc:
            log.warning("Open-Meteo batch failed (attempt %d/%d, %d locations): %s",
                        attempt + 1, ATTEMPTS, len(keys), exc)
            if attempt < ATTEMPTS - 1:
                time.sleep(0.7 * (2 ** attempt))   # 0.7 s, 1.4 s
    return None


def fetch_series(coords) -> dict:
    """coords: iterable of (lat, lng). Returns {key(lat,lng): Series} for every location we could
    get (fresh, cached, or stale). Locations that could not be obtained are simply absent."""
    keys = list(dict.fromkeys(key(lat, lng) for lat, lng in coords))
    found = cache.get_many([_ckey(k) for k in keys])
    result = {k: found[_ckey(k)] for k in keys if _ckey(k) in found}
    missing = [k for k in keys if k not in result]
    if not missing:
        return result

    batches = [missing[i:i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]

    def run(batch):
        series = _fetch_batch(batch)
        if series is not None:  # cache right away so a retried plan only refetches failures
            cache.set_many({_ckey(k): s for k, s in zip(batch, series)}, settings.WEATHER_CACHE_SECONDS)
            cache.set_many({_skey(k): s for k, s in zip(batch, series)}, settings.WEATHER_STALE_SECONDS)
        return batch, series

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        outcomes = list(pool.map(run, batches))

    failed = []
    for batch, series in outcomes:
        if series is None:
            failed.extend(batch)
            continue
        result.update(zip(batch, series))

    if failed:
        stale = cache.get_many([_skey(k) for k in failed])
        for k in failed:
            s = stale.get(_skey(k))
            if s is not None:
                s.stale = True
                result[k] = s
        log.warning("Weather: %d/%d locations unavailable live; %d served from stale cache",
                    len(failed), len(keys), sum(1 for k in failed if k in result))
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
