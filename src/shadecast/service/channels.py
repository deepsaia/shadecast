"""The physical channels with a surrogate: today one, the trees added to the canopy model."""

from __future__ import annotations

from .channel_summary import ChannelSummary
from .unknown_channel import UnknownChannel

CHANNELS = [ChannelSummary(key="treeshade", label="tree shade", kind="tree")]


def channel(key: str) -> ChannelSummary:
    for found in CHANNELS:
        if found.key == key:
            return found
    raise UnknownChannel(key, [found.key for found in CHANNELS])
