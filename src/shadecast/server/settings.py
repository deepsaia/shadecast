"""Everything the server is told, resolved once: a constant, then the environment, then the flags.

No other module reads the environment. A reloading server imports the app by name in a child
process, so the resolved settings travel to it as these variables.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

HOST, PORT, DATA = "SDC_HOST", "SDC_PORT", "SDC_DATA"
STATIC_DIR = Path(__file__).parent / "static"


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    data_root: Path = Path("data")
    static_dir: Path = STATIC_DIR
    reload: bool = False

    @classmethod
    def from_environment(cls) -> ServerSettings:
        values: dict[str, object] = {}
        host = os.environ.get(HOST)
        if host:
            values["host"] = host
        port = os.environ.get(PORT)
        if port:
            values["port"] = int(port)
        data = os.environ.get(DATA)
        if data:
            values["data_root"] = Path(data)
        return cls.model_validate(values)

    def environment(self) -> dict[str, str]:
        """The variables that carry these settings into a reloading child process."""
        return {HOST: self.host, PORT: str(self.port), DATA: str(self.data_root)}

    @property
    def tiles_root(self) -> Path:
        return self.data_root / "tiles"

    @property
    def models_root(self) -> Path:
        return self.data_root / "models"
