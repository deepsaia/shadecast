"""The CoolBench city corpus.

Stratified by Koppen climate zone and World Bank income group, with deliberate
over-sampling of tropical and Global South cities. The 2026 review that found
tropical cities to be only 9% of urban-heat mitigation studies is the reason
this is a design constraint rather than an afterthought.

`in_wri` marks cities that also appear in WRI's Cool Cities Lab. Those are the
cross-validation set: our independently built bundles should agree with their
published UTCI where the two overlap, and any disagreement is informative.

Coordinates are a search *seed*, not the study area. The actual AOI is chosen by
`aoi.select` from population density, so nobody has to hand-tune a box and the
choice is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    key: str
    name: str
    country: str
    lat: float
    lon: float
    koppen: str  # main Koppen-Geiger class
    income: str  # World Bank group: L, LM, UM, H
    region: str
    in_wri: bool = False
    note: str = ""

    @property
    def global_south(self) -> bool:
        return self.income in ("L", "LM", "UM")


_C = [
    # ---- South Asia ----
    City(
        "ahmedabad",
        "Ahmedabad",
        "IND",
        23.0225,
        72.5850,
        "BSh",
        "LM",
        "South Asia",
        note="First Heat Action Plan in South Asia, 2013. Plan-rediscovery validation case.",
    ),
    City("delhi", "Delhi", "IND", 28.6519, 77.2315, "BSh", "LM", "South Asia"),
    City("karachi", "Karachi", "PAK", 24.8607, 67.0011, "BWh", "LM", "South Asia"),
    City("dhaka", "Dhaka", "BGD", 23.7509, 90.3934, "Aw", "LM", "South Asia"),
    City("chennai", "Chennai", "IND", 13.0827, 80.2707, "Aw", "LM", "South Asia"),
    # ---- Southeast Asia ----
    City("jakarta", "Jakarta", "IDN", -6.1751, 106.8272, "Af", "UM", "SE Asia", in_wri=True),
    City("bangkok", "Bangkok", "THA", 13.7563, 100.5018, "Aw", "UM", "SE Asia"),
    City("hochiminh", "Ho Chi Minh City", "VNM", 10.7769, 106.7009, "Aw", "LM", "SE Asia"),
    City("manila", "Manila", "PHL", 14.5995, 120.9842, "Aw", "LM", "SE Asia"),
    # ---- Africa ----
    City("lagos", "Lagos", "NGA", 6.4550, 3.3841, "Aw", "LM", "Africa"),
    City("nairobi", "Nairobi", "KEN", -1.2864, 36.8172, "Cwb", "LM", "Africa", in_wri=True),
    City("accra", "Accra", "GHA", 5.6037, -0.1870, "Aw", "LM", "Africa"),
    City("cairo", "Cairo", "EGY", 30.0444, 31.2357, "BWh", "LM", "Africa"),
    City("daressalaam", "Dar es Salaam", "TZA", -6.7924, 39.2083, "Aw", "LM", "Africa"),
    City("khartoum", "Khartoum", "SDN", 15.5007, 32.5599, "BWh", "L", "Africa"),
    City("johannesburg", "Johannesburg", "ZAF", -26.2041, 28.0473, "Cwb", "UM", "Africa"),
    # ---- Latin America ----
    City("rio", "Rio de Janeiro", "BRA", -22.9068, -43.1729, "Aw", "UM", "LatAm", in_wri=True),
    City("mexicocity", "Mexico City", "MEX", 19.4326, -99.1332, "Cwb", "UM", "LatAm", in_wri=True),
    City("lima", "Lima", "PER", -12.0464, -77.0428, "BWh", "UM", "LatAm"),
    City("saopaulo", "Sao Paulo", "BRA", -23.5505, -46.6333, "Cfa", "UM", "LatAm"),
    City("monterrey", "Monterrey", "MEX", 25.6866, -100.3161, "BSh", "UM", "LatAm"),
    # ---- Middle East ----
    City("dubai", "Dubai", "ARE", 25.2048, 55.2708, "BWh", "H", "Middle East"),
    City("baghdad", "Baghdad", "IRQ", 33.3152, 44.3661, "BWh", "UM", "Middle East"),
    # ---- Europe ----
    City("athens", "Athens", "GRC", 37.9838, 23.7275, "Csa", "H", "Europe"),
    City(
        "seville",
        "Seville",
        "ESP",
        37.3891,
        -5.9845,
        "Csa",
        "H",
        "Europe",
        note="Named and ranked its heatwaves from 2022. Second rediscovery case.",
    ),
    City("milan", "Milan", "ITA", 45.4642, 9.1900, "Cfa", "H", "Europe"),
    City("london", "London", "GBR", 51.5074, -0.1278, "Cfb", "H", "Europe", in_wri=True),
    City("lyon", "Lyon", "FRA", 45.7640, 4.8357, "Cfb", "H", "Europe"),
    # ---- North America ----
    City("phoenix", "Phoenix", "USA", 33.4484, -112.0740, "BWh", "H", "N America"),
    City("boston", "Boston", "USA", 42.3601, -71.0589, "Dfa", "H", "N America", in_wri=True),
    City("houston", "Houston", "USA", 29.7604, -95.3698, "Cfa", "H", "N America"),
    # ---- Oceania ----
    City("sydney", "Sydney", "AUS", -33.8688, 151.2093, "Cfa", "H", "Oceania"),
]

CORPUS: dict[str, City] = {c.key: c for c in _C}


def summary() -> dict:
    n = len(CORPUS)
    south = sum(c.global_south for c in CORPUS.values())
    tropical = sum(c.koppen.startswith("A") for c in CORPUS.values())
    arid = sum(c.koppen.startswith("B") for c in CORPUS.values())
    return {
        "cities": n,
        "global_south": f"{south} ({south / n:.0%})",
        "tropical_A": f"{tropical} ({tropical / n:.0%})",
        "arid_B": f"{arid} ({arid / n:.0%})",
        "southern_hemisphere": sum(c.lat < 0 for c in CORPUS.values()),
        "wri_overlap": sum(c.in_wri for c in CORPUS.values()),
        "regions": len({c.region for c in CORPUS.values()}),
        "koppen_classes": len({c.koppen for c in CORPUS.values()}),
    }
