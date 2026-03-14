"""Configuration loading/saving for downloader server."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

SETTINGS_PATH = Path(os.environ.get("SETTINGS_PATH", "settings.json")).resolve()


@dataclass
class ServerSettings:
    host: str = "127.0.0.1"
    port: int = 5000
    audio_quality: str = "192"
    download_dir: str = "downloads"
    retries: int = 10
    fragment_retries: int = 10


def load_settings() -> ServerSettings:
    if SETTINGS_PATH.exists():
        try:
            raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return ServerSettings(**{**asdict(ServerSettings()), **raw})
        except Exception:
            pass

    settings = ServerSettings(
        audio_quality=os.environ.get("AUDIO_QUALITY", "192"),
        download_dir=os.environ.get("DOWNLOAD_DIR", "downloads"),
    )
    save_settings(settings)
    return settings


def save_settings(settings: ServerSettings) -> None:
    SETTINGS_PATH.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
