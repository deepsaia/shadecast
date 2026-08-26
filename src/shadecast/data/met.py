"""Meteorological forcing in UMEP format, from Open-Meteo's ERA5 archive.

Open-Meteo serves ERA5 reanalysis with no API key and generous limits, which
keeps the build-time pipeline credential-free. The alternative, Copernicus CDS,
requires an account and a .cdsapirc file.

Design-day selection follows the WRI convention: the hottest day observed in a
recent multi-year window, since adaptation should be sized against the extreme
rather than the mean.
"""

from __future__ import annotations

from collections import defaultdict
from operator import itemgetter
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from ..aoi import AOI

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
]

# Column order that solweig_gpu's preprocessor writes and reads back.
UMEP_COLS = [
    "iy",
    "id",
    "it",
    "imin",
    "Q*",
    "QH",
    "QE",
    "Qs",
    "Qf",
    "Wind",
    "RH",
    "Td",
    "press",
    "rain",
    "Kdn",
    "snow",
    "ldown",
    "fcld",
    "wuh",
    "xsmd",
    "lai_hr",
    "Kdiff",
    "Kdir",
    "Wd",
    "uhii",
]
MISSING = -999.0


def fetch_hourly(aoi: AOI, start: str, end: str) -> pd.DataFrame:
    r = requests.get(
        ARCHIVE,
        params={
            "latitude": aoi.lat,
            "longitude": aoi.lon,
            "start_date": start,
            "end_date": end,
            "hourly": ",".join(HOURLY),
            "timezone": "auto",
        },
        timeout=180,
    )
    r.raise_for_status()
    h = r.json()["hourly"]
    df = pd.DataFrame(h)
    df["time"] = pd.to_datetime(df["time"])
    return df


def hottest_day(df: pd.DataFrame) -> str:
    """Date (YYYY-MM-DD) with the highest observed air temperature.

    Adaptation should be sized against the extreme rather than the mean, so the
    design day is the hottest observed in the requested window.
    """
    peaks: dict[str, float] = defaultdict(float)
    for stamp, temperature in zip(df["time"], df["temperature_2m"], strict=True):
        if temperature is None or np.isnan(temperature):
            continue
        day = stamp.strftime("%Y-%m-%d")
        peaks[day] = max(peaks[day], temperature)
    if not peaks:
        raise ValueError("no valid temperatures in the requested window")
    return max(peaks.items(), key=itemgetter(1))[0]


def to_umep(df: pd.DataFrame, date: str) -> pd.DataFrame:
    """Convert one day of Open-Meteo hourly data into a UMEP forcing table."""
    day = df[pd.DatetimeIndex(df["time"]).strftime("%Y-%m-%d") == date].copy()
    if day.empty:
        raise ValueError(f"No met rows for {date}")

    out = pd.DataFrame({name: [MISSING] * len(day) for name in UMEP_COLS})
    stamps = pd.DatetimeIndex(day["time"])
    out["iy"] = stamps.year
    out["id"] = stamps.dayofyear
    out["it"] = stamps.hour
    out["imin"] = 0
    out["Td"] = day["temperature_2m"].to_numpy(dtype=float)  # air temp, degC
    out["RH"] = day["relative_humidity_2m"].to_numpy(dtype=float)  # percent
    out["Wind"] = day["wind_speed_10m"].to_numpy(dtype=float) / 3.6  # km/h -> m/s
    out["Wd"] = day["wind_direction_10m"].to_numpy(dtype=float)  # degrees
    out["press"] = day["surface_pressure"].to_numpy(dtype=float) / 10.0  # hPa -> kPa
    out["Kdn"] = day["shortwave_radiation"].to_numpy(dtype=float)  # W/m2 global
    out["Kdir"] = day["direct_radiation"].to_numpy(dtype=float)
    out["Kdiff"] = day["diffuse_radiation"].to_numpy(dtype=float)
    out["rain"] = 0.0
    out["snow"] = 0.0
    # SOLWEIG derives ldown and cloud fraction itself when these are missing.

    # SOLWEIG cannot use night-time hours with no shortwave input for Tmrt, but
    # it needs the full diurnal cycle for surface heat storage, so keep all 24.
    out["Wind"] = out["Wind"].clip(lower=0.1)  # zero wind breaks the stability calc
    return out[UMEP_COLS]


def write_umep(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep=" ", index=False, float_format="%.4f")
    return path


def build(aoi: AOI, out: Path, start: str, end: str) -> tuple[Path, str]:
    hourly = fetch_hourly(aoi, start, end)
    date = hottest_day(hourly)
    write_umep(to_umep(hourly, date), out)
    return out, date
