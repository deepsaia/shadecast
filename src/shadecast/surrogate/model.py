"""Learned response model: intervention field to cooling field.

The architecture follows directly from the measured physics. Cooling from a new
tree falls from about 18 C at the tree to under 0.1 C by 26 m in dense fabric and
71 m in open treeless fabric, so the response is steeply local but with a tail that
carries the spillover. A convolutional encoder-decoder with roughly a 100 m
receptive field therefore fits the problem: wide enough to see the whole tail, and
local enough that it does not have to learn spurious long-range structure.

The reach is city-dependent, which is why the model is conditioned on local geometry
(building height, existing canopy, sky openness) rather than learning one global
kernel. That conditioning is what should let it transfer.
"""

from __future__ import annotations

import torch
from torch import nn

# placement, baseline Tmrt, building height, canopy height, sky openness,
# is_water, is_vegetated
IN_CHANNELS = 7


class ResponseUNet(nn.Module):
    """Encoder-decoder predicting the cooling field from an intervention field."""

    def __init__(self, in_channels: int = IN_CHANNELS, width: int = 32, depth: int = 4) -> None:
        super().__init__()
        self.depth = depth
        self.encoders = nn.ModuleList()
        self.pools = nn.ModuleList()
        self.decoders = nn.ModuleList()
        self.ups = nn.ModuleList()

        channels = in_channels
        widths: list[int] = []
        for level in range(depth):
            out = width * (2**level)
            self.encoders.append(self._block(channels, out))
            self.pools.append(nn.MaxPool2d(2))
            widths.append(out)
            channels = out

        self.bottleneck = self._block(channels, channels * 2)
        channels *= 2

        for out in reversed(widths):
            self.ups.append(nn.ConvTranspose2d(channels, out, kernel_size=2, stride=2))
            self.decoders.append(self._block(out * 2, out))
            channels = out

        self.head = nn.Conv2d(channels, 1, kernel_size=1)

    @staticmethod
    def _block(in_channels: int, out_channels: int) -> nn.Sequential:
        return nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips: list[torch.Tensor] = []
        for encoder, pool in zip(self.encoders, self.pools, strict=True):
            x = encoder(x)
            skips.append(x)
            x = pool(x)

        x = self.bottleneck(x)

        for up, decoder, skip in zip(self.ups, self.decoders, reversed(skips), strict=True):
            x = up(x)
            x = torch.cat([x, skip], dim=1)
            x = decoder(x)

        # Cooling is non-negative: an added tree never heats a pixel on net over the
        # daylight mean. Softplus enforces that rather than leaving it to be learned.
        return nn.functional.softplus(self.head(x))

    def receptive_field_m(self, res_m: float = 1.0) -> float:
        """Approximate receptive field, for checking it spans the measured reach."""
        field = 1.0
        for _ in range(self.depth):
            field = field * 2 + 4
        return field * 2 * res_m
