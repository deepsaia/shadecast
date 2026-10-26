"""The tiles file of an urban centre: read when present, described and written when not."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from ..corpus import ucdb
from ..corpus.urban_centre import UrbanCentre

logger = logging.getLogger(__name__)

TILES_FILE = "tiles.json"


class TileIndex:
    """One urban centre's 1 km tiles and their attributes, in a file beside its tile directories.

    Describing the tiles needs the centre's polygon and the shared rasters, which is slow and may
    fetch, so the description is written once and read after that. The file is the record.
    """

    def __init__(self, tiles_root: Path, describe: Callable[[UrbanCentre], list[dict]]) -> None:
        self.tiles_root = Path(tiles_root)
        self._describe = describe

    def path(self, centre: UrbanCentre) -> Path:
        return self.tiles_root / str(centre.id) / TILES_FILE

    def rows_if_present(self, urban_centre: int) -> list[dict]:
        """The described tiles when the file exists, else nothing; never describes."""
        path = self.tiles_root / str(urban_centre) / TILES_FILE
        if not path.exists():
            return []
        return json.loads(path.read_text()).get("tiles", [])

    def read_or_describe(self, centre: UrbanCentre) -> dict:
        """The file's payload, describing and writing it first when it does not exist yet."""
        path = self.path(centre)
        if path.exists():
            return json.loads(path.read_text())
        return self.describe_and_write(centre)

    def describe_and_write(self, centre: UrbanCentre) -> dict:
        """Describe every tile again and replace the file."""
        rows = self._describe(centre)
        if not rows:
            raise ValueError(
                f"urban centre {centre.id} ({centre.slug}) has no 1 km tiles to describe"
            )
        payload = {
            "urban_centre": {
                "id": centre.id,
                "slug": centre.slug,
                "name": centre.name,
                "country": centre.country,
                "area_km2": centre.area_km2,
            },
            "release": f"{ucdb.RELEASE} {ucdb.VERSION}",
            "count": len(rows),
            "tiles": rows,
        }
        path = self.path(centre)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
        logger.info("%s: %d tiles written to %s", centre.slug, len(rows), path)
        return payload
