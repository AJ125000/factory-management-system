"""Where the hub keeps its data, and how it listens."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR_NAME = "FMS"


def default_data_dir() -> Path:
    """Per-user app-data folder, overridable with the FMS_DATA_DIR env var."""
    override = os.environ.get("FMS_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "fms"


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=default_data_dir)
    # Localhost only: phones reach the hub through `tailscale serve`, which forwards
    # to this address, so the hub is never exposed on the local network.
    host: str = "127.0.0.1"
    port: int = 8765
    static_dir: Path = Path(__file__).parent / "static"
    auto_backups: bool = True  # daily backups in the background

    @property
    def db_path(self) -> Path:
        return self.data_dir / "fms.db"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"
