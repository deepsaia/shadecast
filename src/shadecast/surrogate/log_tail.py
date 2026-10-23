"""A logging handler that keeps the last few records for a rolling box in a live display."""

from __future__ import annotations

import logging
from collections import deque

TIME_FORMAT = "%H:%M:%S"


class LogTail(logging.Handler):
    """Holds the newest ``keep`` formatted records; older ones roll off the top."""

    def __init__(self, level: int, keep: int = 10) -> None:
        super().__init__(level)
        self.lines: deque[str] = deque(maxlen=keep)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", TIME_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.lines.append(self.format(record))
        except (ValueError, TypeError):  # a bad format string must not kill the run
            self.lines.append(f"{record.levelname} {record.getMessage()}")
