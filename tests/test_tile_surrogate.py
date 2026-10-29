"""A tile's surrogate loads its weights and scene once and predicts any placement after that."""

import numpy as np
import torch
from support import synthetic_tile

from shadecast.surrogate.model import ResponseUNet
from shadecast.surrogate.tile_surrogate import TileSurrogate


def test_a_loaded_surrogate_predicts_a_field_the_size_of_the_tile(tmp_path):
    tile = synthetic_tile.write_bundle(tmp_path)
    synthetic_tile.write_baseline(tile)
    checkpoint = tmp_path / "model.pt"
    torch.save({"state_dict": ResponseUNet(in_channels=7).state_dict(), "in_channels": 7}, checkpoint)
    surrogate = TileSurrogate.load(checkpoint, tile / "bundle", tile / "physics")
    placement = np.zeros((synthetic_tile.SIZE, synthetic_tile.SIZE), dtype=bool)
    placement[10:12, 10:12] = True
    first, seconds = surrogate.predict(placement)
    second, _ = surrogate.predict(placement)
    assert first.shape == placement.shape and first.dtype == np.float32 and seconds >= 0.0
    assert np.array_equal(first, second)
