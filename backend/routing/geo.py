"""Geometry helpers. Coordinates are (lat, lng) rows in numpy arrays."""
import math

import numpy as np

EARTH_RADIUS_MI = 3958.7613


def haversine_mi(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * np.arcsin(np.sqrt(a))


def cumulative_miles(coords) -> np.ndarray:
    coords = np.asarray(coords, dtype=float)
    if len(coords) < 2:
        return np.zeros(len(coords))
    seg = haversine_mi(coords[:-1, 0], coords[:-1, 1], coords[1:, 0], coords[1:, 1])
    return np.concatenate([[0.0], np.cumsum(seg)])


def point_at_mile(coords, cum, mile):
    """Interpolated (lat, lng, segment_index) at `mile` along the polyline."""
    mile = float(min(max(mile, 0.0), cum[-1]))
    i = int(np.searchsorted(cum, mile, side="right")) - 1
    i = min(max(i, 0), len(coords) - 2)
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg <= 0 else (mile - cum[i]) / seg
    lat = coords[i, 0] + t * (coords[i + 1, 0] - coords[i, 0])
    lng = coords[i, 1] + t * (coords[i + 1, 1] - coords[i, 1])
    return float(lat), float(lng), i


def sample_miles(total: float, spacing: float) -> list:
    """Checkpoint miles: 0, spacing, 2*spacing ... and always the final mile."""
    if total <= 0:
        return [0.0]
    miles = [float(m) for m in np.arange(0.0, total, spacing)]
    if len(miles) > 1 and total - miles[-1] < 0.3 * spacing:
        miles.pop()  # avoid a tiny last hop
    miles.append(float(total))
    return miles


def ownership(miles) -> list:
    """Miles of road each checkpoint is responsible for (halfway to each neighbour).

    The values always sum to the route length.
    """
    n = len(miles)
    if n == 1:
        return [0.0]
    out = []
    for i in range(n):
        left = miles[i - 1] if i > 0 else miles[i]
        right = miles[i + 1] if i < n - 1 else miles[i]
        out.append((right - left) / 2.0)
    return out


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def offset_point(lat, lon, bearing, dist_mi):
    d = dist_mi / EARTH_RADIUS_MI
    b = math.radians(bearing)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def bearing_at(coords, i) -> float:
    n = len(coords)
    a, b = (i, min(i + 1, n - 1)) if i < n - 1 else (n - 2, n - 1)
    return bearing_deg(coords[a, 0], coords[a, 1], coords[b, 0], coords[b, 1])


def decimate(coords, cum, step_mi: float) -> np.ndarray:
    """Thin a polyline for display (keeps first/last)."""
    if len(coords) <= 2:
        return np.asarray(coords)
    keep, last = [0], 0
    for i in range(1, len(coords) - 1):
        if cum[i] - cum[last] >= step_mi:
            keep.append(i)
            last = i
    keep.append(len(coords) - 1)
    return np.asarray(coords)[keep]


def resample(coords, cum, n: int) -> np.ndarray:
    """n points evenly spaced by distance (used for route-similarity checks)."""
    pts = [point_at_mile(coords, cum, m)[:2] for m in np.linspace(0, cum[-1], n)]
    return np.asarray(pts)


def fraction_far(a_pts, b_pts, threshold_mi: float) -> float:
    """Share of points in A that are farther than threshold from every point in B."""
    d = haversine_mi(a_pts[:, None, 0], a_pts[:, None, 1], b_pts[None, :, 0], b_pts[None, :, 1])
    return float((d.min(axis=1) > threshold_mi).mean())
