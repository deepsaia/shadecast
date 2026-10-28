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
from torch.nn import functional

from .features import IN_CHANNELS_ORDER

IN_CHANNELS = len(IN_CHANNELS_ORDER)
WIDTH = 32  # channels of the first encoder block; each level doubles it
DEPTH = 4  # pooling levels, which set the receptive field


class ResponseUNet(nn.Module):
    """Encoder-decoder predicting the cooling field from an intervention field."""

    def __init__(
        self, in_channels: int = IN_CHANNELS, width: int = WIDTH, depth: int = DEPTH
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.depth = depth
        self.width = width
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

        # Deliberately unconstrained. An earlier version forced the output
        # non-negative on the assumption that adding a tree can only cool. Measured
        # on real responses that is false: about 0.04 percent of outdoor pixels warm,
        # by up to 10 C, and every one of them sits within 10 m of a new tree. That is
        # the longwave effect of a pixel seeing warm canopy instead of cold sky.
        # Rare, but a model that structurally cannot express it is simply wrong.
        return self.head(x)

    def receptive_field_px(self) -> tuple[int, int]:
        """Smallest and largest receptive field over one pooling cycle, in pixels.

        Probed on a one-dimensional analog of this network with every weight positive and
        average pooling in place of max pooling, so gradient reaches every input pixel. One
        output pixel is back-propagated to the input and the span of nonzero gradient is the
        field. The span varies with the pixel's place inside the 2**depth pixel pooling cell.
        Supports are separable, so the two-dimensional field is this span squared.
        """
        return probe_field(self.depth)

    def receptive_field_m(self, res_m: float = 1.0) -> float:
        """Largest receptive field in metres, for checking it spans the measured reach."""
        return self.receptive_field_px()[1] * res_m


def probe_field(depth: int) -> tuple[int, int]:
    """Minimum and maximum span of input a single output pixel can see, over one pooling cell."""
    cell = 2**depth
    length = cell * 64
    spans = []
    for offset in range(cell):
        line = torch.ones(1, 1, length, requires_grad=True)
        out = line_forward(line, depth)
        out[0, 0, length // 2 + offset].backward()
        if line.grad is None:
            raise RuntimeError("the probe line received no gradient")
        hit = torch.nonzero(line.grad[0, 0]).flatten()
        spans.append(int(hit.max() - hit.min() + 1))
    return min(spans), max(spans)


def line_forward(line: torch.Tensor, depth: int) -> torch.Tensor:
    """The network's geometry on a line: positive weights, average pooling, summed skips.

    Values only grow, so the ReLUs would pass everything and are left out. Only the
    pattern of connections matters for the receptive field, not the values.
    """
    kernel3 = torch.ones(1, 1, 3)
    kernel2 = torch.ones(1, 1, 2)
    skips = []
    for _ in range(depth):
        line = two_convs(line, kernel3)
        skips.append(line)
        line = functional.avg_pool1d(line, 2)
    line = two_convs(line, kernel3)
    for skip in reversed(skips):
        line = functional.conv_transpose1d(line, kernel2, stride=2) + skip
        line = two_convs(line, kernel3)
    return line


def two_convs(line: torch.Tensor, kernel3: torch.Tensor) -> torch.Tensor:
    line = functional.conv1d(line, kernel3, padding=1)
    return functional.conv1d(line, kernel3, padding=1)
