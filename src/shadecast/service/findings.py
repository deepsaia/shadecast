"""What the experiments have established so far, settled or pending, as the walkthrough reads it.

The four summaries keep the shapes their experiment files give them until the client page is
written; each carries a ``status`` of ``done`` or ``pending``.
"""

from __future__ import annotations

from pydantic import BaseModel


class Findings(BaseModel):
    surrogate: dict
    factorial: dict
    targeting: dict
    channel: dict
