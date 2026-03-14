"""yt-dlp downloader wrapper."""

from __future__ import annotations

from pathlib import Path

from yt_dlp import YoutubeDL

from .config import ServerSettings
from .metadata import write_metadata_and_rename


class AudioDownloader:
    def __init__(self, settings: ServerSettings):
        self.settings = settings

    @property
    def download_dir(self) -> Path:
        path = Path(self.settings.download_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def download_audio(self, video_url: str) -> Path:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(self.download_dir / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "retries": self.settings.retries,
            "fragment_retries": self.settings.fragment_retries,
            "continuedl": True,
            "ignoreerrors": False,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.settings.audio_quality,
                }
            ],
            "quiet": True,
            "no_warnings": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

        video_id = info.get("id")
        if not video_id:
            raise RuntimeError("yt-dlp did not return a video id.")

        mp3_path = self.download_dir / f"{video_id}.mp3"
        if not mp3_path.exists():
            found = sorted(
                self.download_dir.glob(f"{video_id}*.mp3"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not found:
                raise FileNotFoundError("Expected mp3 output file not found after download.")
            mp3_path = found[0]

        return write_metadata_and_rename(self.download_dir, mp3_path, info)
