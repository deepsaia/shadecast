"""Errors raised when the external physics engine cannot be reached."""

from __future__ import annotations


class EngineNotFound(RuntimeError):
    """The SOLWEIG console script could not be located.

    shadecast never imports the engine, so a missing engine is a deployment
    problem rather than an import error, and must be reported as such.
    """
