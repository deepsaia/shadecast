"""A raster window is a 100 m read in grid coordinates; blocks inside it are plain slices."""

import numpy as np
import rasterio
from rasterio.transform import from_origin

from shadecast.data.ghs_grid import CRS
from shadecast.data.raster_window import RasterWindow

ORIGIN = (6_897_000.0, 2_809_000.0)  # a window over x 6897..6900 km and y 2807..2809 km


def _window() -> RasterWindow:
    values = np.zeros((20, 30), dtype="float32")
    values[10:20, 0:10] = 2.0  # the cell block at (6897, 2807) holds 2 everywhere
    values[0:10, 10:20] = 5.0  # the cell block at (6898, 2808) holds 5 everywhere
    return RasterWindow(values, ORIGIN)


def test_zeros_covers_the_box_at_one_hundred_metres():
    window = RasterWindow.zeros((6_897_000.0, 2_807_000.0, 6_900_000.0, 2_809_000.0))
    assert window.values.shape == (20, 30)
    assert window.origin == (6_897_000.0, 2_809_000.0)


def test_block_is_the_slice_inside_a_box():
    block = _window().block((6_897_000, 2_807_000, 6_898_000, 2_808_000))
    assert block.shape == (10, 10)
    assert float(block.min()) == float(block.max()) == 2.0


def test_sum_in_a_box():
    assert _window().sum_in((6_898_000, 2_808_000, 6_899_000, 2_809_000)) == 500.0


def test_mean_in_a_box_and_zero_outside_the_window():
    window = _window()
    assert window.mean_in((6_897_000, 2_807_000, 6_898_000, 2_808_000)) == 2.0
    assert window.mean_in((6_950_000, 2_807_000, 6_951_000, 2_808_000)) == 0.0


def test_paste_reads_a_tile_into_the_window_and_zeroes_nodata(tmp_path):
    path = tmp_path / "tile.tif"
    data = np.full((20, 20), 3.0, dtype="float32")
    data[0, 0] = 255.0
    data[1, 1] = -200.0
    transform = from_origin(6_897_000.0, 2_809_000.0, 100.0, 100.0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=1,
        dtype="float32",
        crs=CRS,
        transform=transform,
    ) as dst:
        dst.write(data, 1)
    window = RasterWindow.zeros((6_897_000.0, 2_807_000.0, 6_900_000.0, 2_809_000.0))
    read = window.paste(path, (6_897_000.0, 2_807_000.0, 6_900_000.0, 2_809_000.0), 255.0)
    assert read == 400
    assert window.values[0, 0] == 0.0 and window.values[1, 1] == 0.0
    assert window.values[5, 5] == 3.0
    assert float(window.values[:, 20:].max()) == 0.0
