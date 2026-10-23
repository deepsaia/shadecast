"""Legends for the categorical fields of the urban centre database.

Koppen-Geiger classes arrive as the numeric codes of the Beck et al. 1 km maps, and World Bank
income groups as the database's own strings. Both use `-` for missing, which is reported as
missing rather than guessed, because a stratification built on a guess is not a stratification.
"""

from __future__ import annotations

import math

import pandas as pd

MISSING = "-"

# Beck et al. (2018, 2023) legend, in map order.
KOPPEN: dict[int, str] = {
    1: "Af",
    2: "Am",
    3: "Aw",
    4: "BWh",
    5: "BWk",
    6: "BSh",
    7: "BSk",
    8: "Csa",
    9: "Csb",
    10: "Csc",
    11: "Cwa",
    12: "Cwb",
    13: "Cwc",
    14: "Cfa",
    15: "Cfb",
    16: "Cfc",
    17: "Dsa",
    18: "Dsb",
    19: "Dsc",
    20: "Dsd",
    21: "Dwa",
    22: "Dwb",
    23: "Dwc",
    24: "Dwd",
    25: "Dfa",
    26: "Dfb",
    27: "Dfc",
    28: "Dfd",
    29: "ET",
    30: "EF",
}

# World Bank income group as the database spells it, to the code the corpus stratifies on.
INCOME: dict[str, str] = {
    "Low income": "L",
    "Lower Middle": "LM",
    "Upper Middle": "UM",
    "High income": "H",
}


def is_missing(value: object) -> bool:
    if value is None or value is pd.NA:
        return True
    if isinstance(value, str):
        return value.strip() == MISSING or not value.strip()
    return isinstance(value, float) and math.isnan(value)


def koppen_code(value: object) -> int | None:
    """The Koppen-Geiger code as an integer, or None where the database has none."""
    if is_missing(value):
        return None
    try:
        code = int(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Koppen-Geiger code {value!r} is not a number") from exc
    if KOPPEN.get(code) is None:
        raise ValueError(f"unknown Koppen-Geiger code {code}")
    return code


def koppen_symbol(value: object) -> str | None:
    """The Koppen-Geiger symbol such as BSh, or None where the database has none."""
    code = koppen_code(value)
    return None if code is None else KOPPEN.get(code)


def income_code(group: object) -> str | None:
    """The income code L, LM, UM or H, or None where the database has none."""
    if is_missing(group):
        return None
    code = INCOME.get(str(group).strip())
    if code is None:
        raise ValueError(f"unknown World Bank income group {group!r}")
    return code
