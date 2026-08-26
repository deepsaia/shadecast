"""Check simulated heat against what a satellite actually saw.

**These are not the same quantity, and the comparison must not pretend otherwise.**
Landsat's thermal band gives land surface temperature, the skin temperature of the
ground and roofs. SOLWEIG computes mean radiant temperature, the radiation load a
standing body experiences, which includes sky and wall contributions and is
typically far hotter in sun and cooler in shade than the surface beneath.

So an absolute comparison is meaningless. What is meaningful is whether the model
puts hot places where the satellite sees hot places. That is a spatial pattern
question, answered with rank correlation over the study area, and it is the check a
reviewer will ask for first.

Landsat crosses at roughly 10:30 local, so the simulated hour is matched to the
overpass rather than to the daily peak.
"""

from __future__ import annotations

import logging

import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy import ndimage, stats

from .aoi import AOI

logger = logging.getLogger(__name__)

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
LANDSAT_OVERPASS_HOUR = 10
# Collection 2 Level 2 surface temperature scaling, per USGS product guide.
ST_SCALE, ST_OFFSET = 0.00341802, 149.0
KELVIN = 273.15


def find_scene(aoi: AOI, month: int, max_cloud: int = 20) -> dict | None:
    """The least cloudy Landsat scene over the study area in a given month."""
    catalogue = pystac_client.Client.open(STAC, modifier=pc.sign_inplace)
    search = catalogue.search(
        collections=["landsat-c2-l2"],
        bbox=aoi.bounds_wgs84,
        query={"eo:cloud_cover": {"lt": max_cloud}, "platform": {"in": ["landsat-8", "landsat-9"]}},
    )
    items = [i for i in search.items() if i.datetime is not None and i.datetime.month == month]
    if not items:
        return None
    best = min(items, key=lambda i: i.properties.get("eo:cloud_cover", 100))
    stamp = best.datetime
    assert stamp is not None  # filtered above, but the type checker cannot see it
    return {
        "id": best.id,
        "date": stamp.strftime("%Y-%m-%d"),
        "cloud": best.properties.get("eo:cloud_cover"),
        "href": best.assets["lwir11"].href,
    }


def surface_temperature(href: str, aoi: AOI) -> np.ndarray:
    """Landsat surface temperature in Celsius, on the AOI grid."""
    with rasterio.open(href) as src:
        buffer = np.full(aoi.shape, np.nan, dtype="float32")
        reproject(
            source=rasterio.band(src, 1),
            destination=buffer,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=aoi.transform,
            dst_crs=aoi.crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    kelvin = buffer * ST_SCALE + ST_OFFSET
    celsius = kelvin - KELVIN
    # Landsat thermal is 100 m native, resampled here, so values outside a plausible
    # land-surface range are resampling artefacts rather than measurements.
    celsius[(celsius < -10) | (celsius > 90)] = np.nan
    return celsius


def _smooth_ignoring_gaps(field: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian smooth a field containing NaN without spreading the NaN."""
    present = np.isfinite(field)
    filled = np.where(present, field, 0.0)
    numerator = ndimage.gaussian_filter(filled, sigma=sigma, mode="nearest")
    denominator = ndimage.gaussian_filter(present.astype("float64"), sigma=sigma, mode="nearest")
    out = np.full(field.shape, np.nan)
    usable = denominator > 1e-6
    out[usable] = numerator[usable] / denominator[usable]
    return out


def compare(
    simulated: np.ndarray,
    observed: np.ndarray,
    mask: np.ndarray,
    smooth_m: float = 100.0,
    res_m: float = 1.0,
) -> dict:
    """Rank correlation between simulated and observed heat patterns.

    Both fields are smoothed to Landsat's native 100 m before comparing. Correlating
    a 1 m simulation against a 100 m observation pixel by pixel would mostly measure
    the resampling, not the model.
    """
    sigma = smooth_m / res_m / 2.0

    # Plain Gaussian smoothing propagates NaN across the whole field, which silently
    # invalidates every pixel. Normalised convolution smooths the values and the
    # validity mask separately and divides, so gaps stay local.
    sim = _smooth_ignoring_gaps(np.where(mask, simulated, np.nan), sigma)
    obs = _smooth_ignoring_gaps(observed, sigma)

    valid = mask & np.isfinite(sim) & np.isfinite(obs)
    if valid.sum() < 1000:
        return {"valid_pixels": int(valid.sum()), "usable": False}

    # Subsample to independent samples at the observation scale, so the reported
    # p-value is not inflated by a million correlated pixels.
    step = max(1, int(smooth_m / res_m))
    sub = np.zeros_like(valid)
    sub[::step, ::step] = True
    sample = valid & sub

    spearman = stats.spearmanr(sim[sample], obs[sample])
    pearson = stats.pearsonr(sim[sample], obs[sample])
    return {
        "usable": True,
        "valid_pixels": int(valid.sum()),
        "independent_samples": int(sample.sum()),
        "spearman": round(float(spearman.statistic), 4),
        "spearman_p": float(spearman.pvalue),
        "pearson": round(float(pearson.statistic), 4),
        "simulated_range_C": [
            round(float(np.nanmin(sim[valid])), 1),
            round(float(np.nanmax(sim[valid])), 1),
        ],
        "observed_range_C": [
            round(float(np.nanmin(obs[valid])), 1),
            round(float(np.nanmax(obs[valid])), 1),
        ],
        "note": (
            "Mean radiant temperature and land surface temperature are different "
            "quantities. Only the spatial pattern is comparable, not the values."
        ),
    }
