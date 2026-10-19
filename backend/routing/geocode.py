"""Free-text geocoding via Nominatim (OSM). Accepts "lat,lng" directly."""
import hashlib
import re
import threading
import time

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import PlanningError

_LATLNG = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
_lock = threading.Lock()
_last_call = 0.0  # Nominatim policy: max 1 request/second


def geocode(query: str) -> dict:
    q = (query or "").strip()
    if not q:
        raise PlanningError("Please enter both an origin and a destination.", 400)

    m = _LATLNG.match(q)
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise PlanningError(f"Coordinates out of range: {q}", 422)
        return {"query": q, "name": f"{lat:.4f}, {lng:.4f}", "lat": lat, "lng": lng}

    key = "geo:" + hashlib.md5(q.lower().encode()).hexdigest()
    hit = cache.get(key)
    if hit:
        return hit

    global _last_call
    with _lock:
        wait = 1.1 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = requests.get(
                settings.NOMINATIM_URL,
                params={"q": q, "format": "jsonv2", "limit": 1},
                headers={"User-Agent": settings.HTTP_USER_AGENT},
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise PlanningError("The geocoding service is unavailable. Try again shortly.", 502) from exc
        finally:
            _last_call = time.monotonic()

    if not results:
        raise PlanningError(f"Could not find a location matching “{q}”.", 422)
    top = results[0]
    out = {"query": q, "name": top.get("display_name", q), "lat": float(top["lat"]), "lng": float(top["lon"])}
    cache.set(key, out, settings.GEOCODE_CACHE_SECONDS)
    return out
