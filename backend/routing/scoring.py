"""Route scoring and recommendation.

Each checkpoint "owns" the miles of road around it (segment_miles); those miles
are attributed to the checkpoint's risk level.
"""
from dataclasses import dataclass, field
from .risk import LEVEL_NAMES


@dataclass
class Checkpoint:
    mile: float
    level: int
    segment_miles: float


@dataclass
class RouteScore:
    route_id: str
    duration_s: float
    distance_mi: float
    miles_by_level: dict = field(default_factory=dict)
    avg_risk: float = 0.0


def score_route(route_id, duration_s, distance_mi, checkpoints) -> RouteScore:
    miles = {name: 0.0 for name in LEVEL_NAMES}
    weighted = 0.0
    for cp in checkpoints:
        miles[LEVEL_NAMES[cp.level]] += cp.segment_miles
        weighted += cp.level * cp.segment_miles
    total = sum(cp.segment_miles for cp in checkpoints) or 1.0
    return RouteScore(route_id, duration_s, distance_mi, miles, weighted / total)


def rank_key(r: RouteScore):
    # No Travel first (implied worse than Severe), then the brief's 4 priorities.
    # Miles are rounded to whole miles so trivial differences don't beat a much faster route.
    return (
        round(r.miles_by_level["no_travel"]),
        round(r.miles_by_level["severe"]),
        round(r.miles_by_level["high"]),
        round(r.avg_risk, 2),
        r.duration_s,
    )


def rank_routes(routes):
    return sorted(routes, key=rank_key)


def explain(best: RouteScore, others) -> str:
    if not others:
        return "Only one route available."
    m = best.miles_by_level
    for label, key in (("No Travel", "no_travel"), ("Severe", "severe"), ("High", "high")):
        theirs = [round(o.miles_by_level[key]) for o in others]
        if round(m[key]) < max(theirs):
            return (f"Fewest {label} miles: {round(m[key])} mi vs "
                    f"{', '.join(str(t) for t in theirs)} on the alternatives.")
    return (f"Lowest average risk ({best.avg_risk:.2f}) among routes with equal "
            f"Severe/High exposure; ties broken by shortest travel time.")
