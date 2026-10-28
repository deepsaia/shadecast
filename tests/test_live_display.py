"""The live display keeps log records in its box while it runs and restores the terminal after."""

import logging
from io import StringIO

from rich.console import Console
from rich.text import Text

from shadecast.surrogate.live_display import LiveDisplay, clock, sparkline


def _console() -> Console:
    return Console(file=StringIO(), width=100, force_terminal=False, color_system=None)


def test_records_go_into_the_box_while_live_and_the_handlers_come_back_after():
    root = logging.getLogger()
    marker = logging.NullHandler()
    root.addHandler(marker)
    display = LiveDisplay(_console(), lambda: Text("view"))
    try:
        display.start()
        assert marker not in root.handlers
        logging.getLogger("shadecast.test_live_display").warning("slow epoch")
        box = display.log_box()
        assert box is not None and "slow epoch" in str(box.renderable)
        display.stop()
        assert marker in root.handlers and display.live is None
    finally:
        root.removeHandler(marker)


def test_a_quiet_display_renders_nothing_and_has_no_box():
    display = LiveDisplay(None, lambda: Text("view"))
    display.start()
    display.refresh()
    assert display.live is None and display.log_box() is None
    display.stop()


def test_sparkline_and_clock():
    assert sparkline([1.0, 2.0, 3.0]) == "▁▄█"
    assert sparkline([2.0, 2.0]) == "▄▄"
    assert sparkline([]) == ""
    assert clock(65) == "1m 05s"
    assert clock(3725) == "1h 02m"
