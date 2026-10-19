"""Weather risk classification.

Levels are ints so they can be compared, averaged and used as heatmap weights.
Boundary rules (from the brief):
  Wind : <25 low | 25-34 mod | 35-44 high | 45-54 severe | >=55 no travel
  Rain : <0.10 low | 0.10-0.25 mod | 0.25-0.50 high | 0.50-1.00 severe | >1.00 no travel
  Snow : <0.5 low | 0.5-1.0 mod | 1.0-2.0 high | 2.0-3.0 severe | >3.0 no travel
Lower bound inclusive, so exactly 0.25 in/hr rain is High, exactly 1.00 is Severe.
"""
from dataclasses import dataclass

LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL = range(5)
LEVEL_NAMES = ["low", "moderate", "high", "severe", "no_travel"]

# Heavy-load thresholds (lb)
LOAD_NO_TRAVEL_LB = 30_000   # with wind 45-54
LOAD_SEVERE_LB = 40_000      # with wind 35-44


def _bucket(value: float, lower_bounds: tuple) -> int:
    """lower_bounds = inclusive lower bounds of moderate, high, severe, no_travel."""
    level = LOW
    for i, bound in enumerate(lower_bounds, start=1):
        if value >= bound:
            level = i
    return level


def wind_level(mph: float) -> int:
    return _bucket(mph, (25, 35, 45, 55))


def rain_level(in_hr: float) -> int:
    # "0.50-1.00" is severe, ">1.00" is no travel -> strictly greater than
    if in_hr > 1.00:
        return NO_TRAVEL
    return _bucket(in_hr, (0.10, 0.25, 0.50))


def snow_level(in_hr: float) -> int:
    if in_hr > 3.0:
        return NO_TRAVEL
    return _bucket(in_hr, (0.5, 1.0, 2.0))


@dataclass(frozen=True)
class RiskResult:
    level: int
    wind: int
    rain: int
    snow: int
    reason: str

    @property
    def name(self) -> str:
        return LEVEL_NAMES[self.level]


def classify(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> RiskResult:
    """Overall risk = worst of wind/rain/snow, with load rules escalating wind."""
    wind = wind_level(wind_mph)
    reason = ""
    if wind_mph >= 55:
        wind, reason = NO_TRAVEL, "wind >= 55 mph"
    elif wind_mph >= 45 and load_lb > LOAD_NO_TRAVEL_LB:
        wind, reason = NO_TRAVEL, "wind 45-54 mph with load > 30,000 lb"
    elif wind_mph >= 35 and load_lb > LOAD_SEVERE_LB:
        if wind < SEVERE:
            wind, reason = SEVERE, "wind 35-44 mph with load > 40,000 lb"
    rain, snow = rain_level(rain_in_hr), snow_level(snow_in_hr)
    level = max(wind, rain, snow)
    if not reason or level != wind:
        driver = max((("wind", wind), ("rain", rain), ("snow", snow)), key=lambda p: p[1])
        reason = f"{driver[0]} is {LEVEL_NAMES[driver[1]]}"
    return RiskResult(level, wind, rain, snow, reason)
