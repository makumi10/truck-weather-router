"""Orchestrates one trip plan: geocode -> routes -> checkpoints/ETAs -> weather -> risk -> ranking."""
import math
from datetime import datetime, timedelta, timezone

from django.conf import settings

from . import geo, geocode, osrm, weather
from .risk import LEVEL_NAMES, classify
from .scoring import Checkpoint, explain, rank_routes, score_route

MAX_CHECKPOINTS = 300
HEAT_HOURS = 48
MAX_HEAT_POINTS = 450
LABELS = "ABC"


def choose_spacing(choice, total_mi: float) -> float:
    """10/25/50 miles. 'auto' scales with trip length; a fixed choice is capped so a
    long trip can't explode into thousands of checkpoints."""
    if str(choice) != "auto":
        spacing = float(choice)
    else:
        spacing = 10.0 if total_mi < 150 else 25.0 if total_mi < 500 else 50.0
    if total_mi / spacing + 1 > MAX_CHECKPOINTS:
        spacing = total_mi / (MAX_CHECKPOINTS - 1)
    return spacing


def _corridor_points(routes) -> list:
    """Grid for the heatmap: points along each route plus lateral offsets either side."""
    longest = max(r.distance_mi for r in routes)
    spacing = min(40.0, max(5.0, longest / 40.0))
    lateral = min(15.0, max(3.0, spacing * 0.6))
    pts = {}
    for r in routes:
        for m in geo.sample_miles(r.distance_mi, spacing):
            lat, lng, i = geo.point_at_mile(r.coords, r.cum, m)
            hdg = geo.bearing_at(r.coords, i)
            pts[weather.key(lat, lng)] = (lat, lng)
            for side in (90, -90):
                olat, olng = geo.offset_point(lat, lng, hdg + side, lateral)
                pts[weather.key(olat, olng)] = (olat, olng)
    out = list(pts.values())
    if len(out) > MAX_HEAT_POINTS:
        out = out[:: math.ceil(len(out) / MAX_HEAT_POINTS)]
    return out


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def plan_trip(origin: str, destination: str, departure: datetime, load_lb: float,
              spacing_choice="auto", now: datetime = None) -> dict:
    now = now or datetime.now(timezone.utc)
    o = geocode.geocode(origin)
    d = geocode.geocode(destination)
    routes = osrm.get_routes(o, d, want=3)
    dep_epoch = departure.timestamp()

    # 1. checkpoints + ETAs for every route
    built = []
    for idx, r in enumerate(routes):
        spacing = choose_spacing(spacing_choice, r.distance_mi)
        miles = geo.sample_miles(r.distance_mi, spacing)
        own = geo.ownership(miles)
        travel_s = r.duration_s * settings.TRUCK_TIME_FACTOR
        cps = []
        for m, seg in zip(miles, own):
            lat, lng, _ = geo.point_at_mile(r.coords, r.cum, m)
            frac = m / r.distance_mi if r.distance_mi else 0.0
            cps.append({"mile": m, "lat": lat, "lng": lng, "segment_miles": seg,
                        "eta_epoch": dep_epoch + travel_s * frac})
        built.append({"route": r, "spacing": spacing, "checkpoints": cps, "travel_s": travel_s, "label": LABELS[idx]})

    heat_pts = _corridor_points(routes)

    # 2. one batched weather fetch (cached) for checkpoints + heatmap grid
    coords = [(c["lat"], c["lng"]) for b in built for c in b["checkpoints"]] + heat_pts
    series_by_key = weather.fetch_series(coords)

    # 3. weather -> risk per checkpoint, then score each route
    scores, payload_routes = [], []
    for b in built:
        r = b["route"]
        out_cps, score_cps, clamped_any = [], [], False
        for c in b["checkpoints"]:
            s = series_by_key[weather.key(c["lat"], c["lng"])]
            w = weather.sample(s, c["eta_epoch"])
            risk = classify(w["wind"], w["rain"], w["snow"], load_lb)
            clamped_any |= w["clamped"]
            score_cps.append(Checkpoint(c["mile"], risk.level, c["segment_miles"]))
            out_cps.append({
                "mile": round(c["mile"], 1), "lat": round(c["lat"], 5), "lng": round(c["lng"], 5),
                "eta": _iso(c["eta_epoch"]), "forecast_time": _iso(w["hour_epoch"]),
                "forecast_clamped": w["clamped"], "segment_miles": round(c["segment_miles"], 1),
                "wind_mph": round(w["wind"], 1), "rain_in_hr": round(w["rain"], 3),
                "snow_in_hr": round(w["snow"], 3),
                "level": risk.level, "level_name": risk.name, "reason": risk.reason,
            })
        sc = score_route(b["label"], b["travel_s"], r.distance_mi, score_cps)
        scores.append(sc)
        display = geo.decimate(r.coords, r.cum, max(0.1, r.distance_mi / 1500.0))
        payload_routes.append({
            "label": b["label"], "checkpoint_spacing_mi": round(b["spacing"], 1),
            "geometry": [[round(float(la), 5), round(float(ln), 5)] for la, ln in display],
            "checkpoints": out_cps,
            "summary": {
                "distance_mi": round(r.distance_mi, 1), "duration_s": round(b["travel_s"]),
                "arrival": _iso(dep_epoch + b["travel_s"]),
                "miles_by_level": {k: round(v, 1) for k, v in sc.miles_by_level.items()},
                "avg_risk": round(sc.avg_risk, 2),
                "worst_level": LEVEL_NAMES[max(cp["level"] for cp in out_cps)],
                "forecast_clamped": clamped_any,
            },
        })

    ranked = rank_routes(scores)
    best = ranked[0]
    reason = explain(best, [s for s in ranked[1:]])
    rank_of = {s.route_id: i + 1 for i, s in enumerate(ranked)}
    for pr in payload_routes:
        pr["rank"] = rank_of[pr["label"]]
        pr["recommended"] = pr["label"] == best.route_id
    payload_routes.sort(key=lambda p: p["rank"])

    # 4. heatmap: 49 hourly risk levels per grid point, computed once, scrubbed client-side
    start_epoch = int(now.timestamp() // 3600 * 3600)
    heat = []
    for lat, lng in heat_pts:
        s = series_by_key[weather.key(lat, lng)]
        levels = []
        for h in range(HEAT_HOURS + 1):
            i, _ = weather.hour_index(s, start_epoch + h * 3600)
            levels.append(classify(s.wind[i], s.rain[i], s.snow[i], load_lb).level)
        heat.append([round(lat, 4), round(lng, 4), levels])

    notes = ["Routes come from OSRM's car profile (no truck restrictions); ETAs scale OSRM durations."]
    if any(r["summary"]["forecast_clamped"] for r in payload_routes):
        notes.append("Some ETAs fall outside the available forecast window; the nearest forecast hour was used.")

    return {
        "request": {"origin": o, "destination": d, "departure": _iso(dep_epoch), "load_weight_lb": load_lb,
                    "checkpoint_spacing": str(spacing_choice)},
        "routes": payload_routes,
        "recommendation": {"label": best.route_id, "reason": reason},
        "heatmap": {"start": _iso(start_epoch), "hours": HEAT_HOURS, "points": heat},
        "notes": notes,
    }
