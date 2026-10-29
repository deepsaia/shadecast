"""The noon sun from latitude and date: the two constant channels the surrogate reads."""

import pytest

from shadecast.surrogate.sun import SunNoon
from shadecast.surrogate.sun import declination_deg


def test_declination_peaks_at_the_solstices():
    assert declination_deg(172) == pytest.approx(23.44, abs=0.1)  # 21 June
    assert declination_deg(355) == pytest.approx(-23.44, abs=0.1)  # 21 December


def test_declination_is_near_zero_at_the_equinoxes():
    """Cooper's formula is about a degree off at the September equinox; that is its known error."""
    assert declination_deg(80) == pytest.approx(0.0, abs=1.5)  # 21 March
    assert declination_deg(266) == pytest.approx(0.0, abs=1.5)  # 23 September


def test_the_equinox_sun_is_overhead_at_the_equator():
    sun = SunNoon.for_day(0.0, "2024-03-20")
    assert sun.elevation_deg == pytest.approx(90.0, abs=1.0)


def test_ahmedabad_design_day_has_a_high_southern_sun():
    """23 N on 2024-05-23: declination about 20.6, so the sun is 2.4 degrees south of zenith."""
    sun = SunNoon.for_day(23.014, "2024-05-23")
    assert sun.declination_deg == pytest.approx(20.6, abs=0.3)
    assert sun.elevation_deg == pytest.approx(87.6, abs=0.3)
    assert sun.side == 1.0


def test_a_southern_city_in_january_sees_the_sun_to_the_north():
    sun = SunNoon.for_day(-33.87, "2024-01-15")  # Sydney
    assert sun.azimuth_deg == 0.0
    assert sun.side == -1.0
    assert sun.elevation_deg == pytest.approx(90.0 - (33.87 - 21.3), abs=0.5)


def test_a_tropical_city_can_see_the_sun_on_either_side():
    lagos = 6.45
    assert SunNoon.for_day(lagos, "2024-06-21").side == -1.0  # declination above the latitude
    assert SunNoon.for_day(lagos, "2024-12-21").side == 1.0
