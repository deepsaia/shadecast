"""Print the server's OpenAPI schema, so the client's types are generated from the one contract.

Run as ``python -m shadecast.server.openapi``. Needs no running server and no data: the schema
is a property of the routes and their models.
"""

from __future__ import annotations

import json
import sys

from .app import build_app
from .services import Services
from .settings import ServerSettings


def main() -> int:
    settings = ServerSettings()
    schema = build_app(settings, Services.open(settings)).openapi()
    json.dump(schema, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
