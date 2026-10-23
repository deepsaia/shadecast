"""The rolling log box keeps the newest records at or above its level."""

import logging

from shadecast.surrogate.log_tail import LogTail


def test_tail_keeps_the_newest_lines_and_filters_by_level():
    tail = LogTail(logging.WARNING, keep=2)
    log = logging.getLogger("shadecast.test_log_tail")
    log.addHandler(tail)
    log.setLevel(logging.DEBUG)
    try:
        log.info("quiet")
        log.warning("one")
        log.warning("two")
        log.error("three")
    finally:
        log.removeHandler(tail)
    assert [line.split()[-1] for line in tail.lines] == ["two", "three"]
    assert all("WARNING" in line or "ERROR" in line for line in tail.lines)
