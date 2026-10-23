"""The baseline run's sky view factor and shadow stack become two input channels, cached once."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from shadecast.pipeline import DAYLIGHT_BANDS
from shadecast.surrogate import engine_layers

SIDE = 16


def _write(path: Path, bands: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=SIDE,
        height=SIDE,
        count=bands.shape[0],
        dtype="float32",
        crs="EPSG:32643",
        transform=from_origin(249000, 2548000, 1, 1),
    ) as raster:
        raster.write(bands.astype("float32"))


def _baseline(tmp_path: Path) -> Path:
    baseline = tmp_path / "baseline"
    svf = np.linspace(0, 1, SIDE * SIDE, dtype="float32").reshape(1, SIDE, SIDE)
    _write(baseline / engine_layers.SVF_FILE, svf)
    shadow = np.zeros((24, SIDE, SIDE), dtype="float32")
    shadow[12] = 1.0  # the sun reaches everything at noon only
    shadow[:, 0, 0] = 1.0  # one pixel is always lit
    _write(baseline / engine_layers.SHADOW_FILE, shadow)
    return baseline


def test_sky_view_factor_is_read_and_cached(tmp_path):
    baseline = _baseline(tmp_path)
    svf = engine_layers.sky_view_factor(baseline)
    assert svf.shape == (SIDE, SIDE)
    assert svf.min() == 0.0 and svf.max() == 1.0
    assert (baseline / engine_layers.SVF_CACHE).exists()
    assert np.array_equal(engine_layers.sky_view_factor(baseline), svf)


def test_sunlit_fraction_averages_the_daylight_bands(tmp_path):
    baseline = _baseline(tmp_path)
    sunlit = engine_layers.sunlit_fraction(baseline)
    assert sunlit[0, 0] == pytest.approx(1.0)
    assert sunlit[5, 5] == pytest.approx(1.0 / len(DAYLIGHT_BANDS))
    assert (baseline / engine_layers.SUNLIT_CACHE).exists()


def test_a_missing_engine_file_is_named(tmp_path):
    with pytest.raises(FileNotFoundError, match="sky view factor"):
        engine_layers.sky_view_factor(tmp_path / "nowhere")
    with pytest.raises(FileNotFoundError, match="shadow stack"):
        engine_layers.sunlit_fraction(tmp_path / "nowhere")
