"""The one line a failure is reported as, whatever the exception type wraps it in."""

from __future__ import annotations

from pydantic import ValidationError

VALUE_ERROR_PREFIX = "Value error, "  # pydantic's label on a message a validator raised


def error_message(error: BaseException) -> str:
    """The message as written: a KeyError without its quotes, a validation error without its scaffolding."""
    if isinstance(error, ValidationError):
        return "; ".join(str(item.get("msg", "")).removeprefix(VALUE_ERROR_PREFIX) for item in error.errors())
    if isinstance(error, KeyError) and error.args:
        return str(error.args[0])
    return str(error)
