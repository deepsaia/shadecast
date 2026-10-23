"""A raster window is a 100 m read in grid coordinates, read through footprints."""

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from shadecast.data.ghs_grid import CRS
from shadecast.data.raster_window import RasterWindow

BOUNDS = (6_897_000.0, 2_807_000.0, 6_900_000.0, 2_809_000.0)  # 30 by 20 cells


def _window() -> RasterWindow:
    window = RasterWindow.zeros(BOUNDS)
    window.values[10:20, 0:10] = 2.0  # the block at x 6897..6898 km, y 2807..2808 km holds 2
    window.values[0:10, 10:20] = 5.0  # the block at x 6898..6899 km, y 2808..2809 km holds 5
    return window


def test_zeros_covers_the_box_at_one_hundred_metres():
    window = RasterWindow.zeros(BOUNDS)
    assert window.values.shape == (20, 30)
    assert window.origin == (6_897_000.0, 2_809_000.0)


def test_mask_marks_the_cells_whose_centres_lie_inside_a_footprint():
    mask = _window().mask(box(6_897_000, 2_807_000, 6_898_000, 2_808_000))
    assert mask.sum() == 100
    assert mask[10:20, 0:10].all()


def test_inside_and_sum_inside_read_through_the_footprint():
    window = _window()
    assert window.sum_inside(box(6_898_000, 2_808_000, 6_899_000, 2_809_000)) == 500.0
    assert set(window.inside(box(6_897_000, 2_807_000, 6_898_000, 2_808_000)).tolist()) == {2.0}
    assert window.sum_inside(box(6_950_000, 2_807_000, 6_951_000, 2_808_000)) == 0.0


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
    window = RasterWindow.zeros(BOUNDS)
    assert window.paste(path, BOUNDS, 255.0) == 400
    assert window.values[0, 0] == 0.0 and window.values[1, 1] == 0.0
    assert window.values[5, 5] == 3.0
    assert float(window.values[:, 20:].max()) == 0.0
