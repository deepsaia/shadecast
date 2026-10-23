"""Where the sun stands at solar noon on the design day.

Two numbers condition the surrogate on the sun. How high it climbs at noon sets how short
the shadows get. Whether it stands to the south or the north sets the side the shadows
fall on. Both follow from latitude and the day of the year through the solar declination,
by Cooper's formula (cited as cooper_1969). They are broadcast over the grid as constant
channels, so a model trained on several cities and days can tell them apart, and a flip
of the map is a valid augmentation only when the side channel flips with it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

TILT_DEG = 23.44
SOUTH_DEG = 180.0
NORTH_DEG = 0.0


@dataclass(frozen=True)
class SunNoon:
    declination_deg: float
    elevation_deg: float
    azimuth_deg: float  # 180 when the noon sun is due south, 0 when due north

    @classmethod
    def for_day(cls, lat: float, design_day: str) -> SunNoon:
        """The noon sun at a latitude on an ISO date."""
        day_of_year = date.fromisoformat(design_day).timetuple().tm_yday
        declination = declination_deg(day_of_year)
        elevation = 90.0 - abs(lat - declination)
        azimuth = SOUTH_DEG if lat >= declination else NORTH_DEG
        return cls(round(declination, 3), round(elevation, 3), azimuth)

    @property
    def side(self) -> float:
        """+1 when the noon sun is to the south, -1 when it is to the north."""
        return 1.0 if self.azimuth_deg == SOUTH_DEG else -1.0


def declination_deg(day_of_year: int) -> float:
    """Solar declination by Cooper's formula, within about two degrees of the true value."""
    return TILT_DEG * math.sin(math.radians(360.0 / 365.0 * (284 + day_of_year)))
