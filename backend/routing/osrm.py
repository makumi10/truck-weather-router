"""OSRM routing client: returns up to 3 *distinct* routes.

The public demo server often returns fewer than 3 alternatives, so when that
happens we force extra candidates by routing through a via-point pushed to
either side of the fastest route, then drop near-duplicates.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np
import requests
from django.conf import settings
from django.core.cache import cache

from . import geo
from .errors import PlanningError

log = logging.getLogger(__name__)
METERS_PER_MILE = 1609.344
SIMILARITY_SAMPLES = 60
FAR_THRESHOLD_MI = 1.5      # a point this far from the other route is "different road"
MIN_DISTINCT_FRACTION = 0.08  # >=8% of the route must differ to count as an alternative
MAX_DETOUR_FACTOR = 2.0       # ignore silly alternatives >2x slower than the fastest


@dataclass
class Route:
    coords: np.ndarray   # (N, 2) lat,lng
    cum: np.ndarray      # cumulative miles per vertex, scaled to distance_mi
    distance_mi: float
    duration_s: float


def _parse(raw: dict) -> Route:
    coords = np.array([[lat, lng] for lng, lat in raw["geometry"]["coordinates"]], dtype=float)
    if len(coords) < 2:
        raise PlanningError("Routing service returned an empty route.", 502)
    distance_mi = raw["distance"] / METERS_PER_MILE
    cum = geo.cumulative_miles(coords)
    if cum[-1] > 0:
        cum = cum * (distance_mi / cum[-1])  # make geometry agree with OSRM's own distance
    return Route(coords=coords, cum=cum, distance_mi=distance_mi, duration_s=float(raw["duration"]))


def _request(points, alternatives) -> list:
    path = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in points)
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": str(alternatives).lower() if isinstance(alternatives, bool) else str(alternatives),
    }
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{path}"
    last_exc = None
    for _ in range(2):
        try:
            resp = requests.get(url, params=params, headers={"User-Agent": settings.HTTP_USER_AGENT}, timeout=25)
            data = resp.json()
            if data.get("code") == "NoRoute":
                raise PlanningError("No drivable route was found between those locations.", 422)
            if resp.status_code >= 500 or data.get("code") != "Ok":
                last_exc = PlanningError(f"Routing service error: {data.get('code', resp.status_code)}", 502)
                continue
            return data["routes"]
        except PlanningError:
            raise
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
    raise PlanningError("The routing service is unavailable. Try again shortly.", 502) from last_exc


def _samples(route: Route) -> np.ndarray:
    return geo.resample(route.coords, route.cum, SIMILARITY_SAMPLES)


def is_distinct(candidate: Route, accepted) -> bool:
    cs = _samples(candidate)
    for other in accepted:
        os_ = _samples(other)
        diff = max(
            geo.fraction_far(cs, os_, FAR_THRESHOLD_MI),
            geo.fraction_far(os_, cs, FAR_THRESHOLD_MI),
        )
        if diff < MIN_DISTINCT_FRACTION:
            return False
    return True


def _via_candidates(base: Route, origin, dest):
    off = min(35.0, max(4.0, 0.12 * base.distance_mi))
    for frac in (0.5, 0.35):
        lat, lng, i = geo.point_at_mile(base.coords, base.cum, base.distance_mi * frac)
        hdg = geo.bearing_at(base.coords, i)
        for side in (90, -90):
            v = geo.offset_point(lat, lng, hdg + side, off)
            yield [origin, v, dest]


def get_routes(origin: dict, dest: dict, want: int = 3) -> list:
    o, d = (origin["lat"], origin["lng"]), (dest["lat"], dest["lng"])
    ckey = f"osrm:{o[0]:.4f},{o[1]:.4f}:{d[0]:.4f},{d[1]:.4f}:{want}"
    hit = cache.get(ckey)
    if hit:
        return hit
    routes = []
    for raw in _request([o, d], alternatives=want):
        r = _parse(raw)
        if is_distinct(r, routes):
            routes.append(r)

    if len(routes) < want:
        base = routes[0]
        cands = list(_via_candidates(base, o, d))

        def fetch(points):
            try:
                return _parse(_request(points, alternatives=False)[0])
            except (PlanningError, KeyError, IndexError) as exc:
                log.info("via candidate failed: %s", exc)
                return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(fetch, cands))
        for r in results:
            if len(routes) >= want:
                break
            if r and r.duration_s <= MAX_DETOUR_FACTOR * base.duration_s and is_distinct(r, routes):
                routes.append(r)

    routes.sort(key=lambda r: r.duration_s)
    routes = routes[:want]
    cache.set(ckey, routes, 3600)  # road geometry is stable; repeat trips skip routing entirely
    return routes
