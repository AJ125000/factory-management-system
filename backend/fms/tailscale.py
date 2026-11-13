"""Find the laptop's private Tailscale address, so phones know where to connect.

Read-only: runs `tailscale status --json` if Tailscale is installed. Never changes
any Tailscale setting.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

KNOWN_PATHS = [
    r"C:\Program Files\Tailscale\tailscale.exe",
    "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
]


class TailscaleInfo(BaseModel):
    installed: bool
    running: bool
    dns_name: str | None = None

    @property
    def url(self) -> str | None:
        # `tailscale serve` publishes the hub at https://<machine>.<tailnet>.ts.net/
        return f"https://{self.dns_name}/" if self.running and self.dns_name else None


def find_cli() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    return next((p for p in KNOWN_PATHS if Path(p).is_file()), None)


def detect(cli: str | None = None, timeout: float = 4.0) -> TailscaleInfo:
    cli = cli or find_cli()
    if not cli:
        return TailscaleInfo(installed=False, running=False)
    try:
        result = subprocess.run(
            [cli, "status", "--json"], capture_output=True, text=True, timeout=timeout, check=False
        )
        status = json.loads(result.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return TailscaleInfo(installed=True, running=False)
    dns_name = (status.get("Self") or {}).get("DNSName", "").rstrip(".") or None
    return TailscaleInfo(
        installed=True,
        running=status.get("BackendState") == "Running",
        dns_name=dns_name,
    )
