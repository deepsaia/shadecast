"""How a command ends when it cannot do what was asked: one line on stderr and one exit code.

0 is success. 2 says the command line was wrong: a city, tile, model or channel that does not
exist, or options that do not go together; fix the invocation. 1 says the invocation was fine
and the work could not be done: a stage this one needs has not run, or a stage failed. 130 is
a stop with Ctrl-C, after the command has said how to resume. Scripts branch on these.
"""

from __future__ import annotations

from typing import NoReturn

import typer

from .console import error_console
from .service.unknown_channel import UnknownChannel
from .service.unknown_city import UnknownCity
from .service.unknown_model import UnknownModel
from .service.unknown_tile import UnknownTile

FAILED = 1
BAD_ARGUMENTS = 2
STOPPED = 130
# MissingStage is a LookupError too, but it is about the data, not the command line.
BAD_ARGUMENT_ERRORS: tuple[type[Exception], ...] = (
    UnknownCity,
    UnknownTile,
    UnknownModel,
    UnknownChannel,
    ValueError,
    KeyError,
)


def exit_code(error: Exception) -> int:
    """2 for a wrong command line, 1 for work that could not be done."""
    return BAD_ARGUMENTS if isinstance(error, BAD_ARGUMENT_ERRORS) else FAILED


def message(error: Exception) -> str:
    """The message as written; a KeyError would print its own in quotes."""
    if isinstance(error, KeyError) and error.args:
        return str(error.args[0])
    return str(error)


def fail(error: Exception) -> NoReturn:
    """Print the message on stderr, plain, and leave with the code the error's kind deserves."""
    error_console.print(message(error), style="red", markup=False)
    raise typer.Exit(code=exit_code(error)) from error
