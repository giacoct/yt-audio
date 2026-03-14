"""Audio metadata cleanup and file naming."""

from __future__ import annotations

import re
from pathlib import Path

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

NOISE_PATTERNS = [
    r"\(official\s*(video|audio)\)",
    r"\[official\s*(video|audio)\]",
    r"\(lyrics?\)",
    r"\[lyrics?\]",
    r"\b4k\b",
    r"\bhd\b",
    r"\bhq\b",
    r"\bvisuali[sz]er\b",
    r"\(audio\)",
    r"\[audio\]",
]


def clean_title(raw_title: str) -> str:
    title = raw_title or "Unknown Title"
    for pattern in NOISE_PATTERNS:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)
    title = re.sub(r"[_|]+", " ", title)
    title = re.sub(r"\s+-\s+", " - ", title)
    title = re.sub(r"\s{2,}", " ", title).strip(" -_[]()")
    return title or "Unknown Title"


def safe_filename(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", text).strip() or "Unknown"


def choose_output_path(download_dir: Path, artist: str, title: str) -> Path:
    base_name = safe_filename(f"{artist} - {title}")
    candidate = download_dir / f"{base_name}.mp3"
    counter = 1
    while candidate.exists():
        candidate = download_dir / f"{base_name} ({counter}).mp3"
        counter += 1
    return candidate


def write_metadata_and_rename(download_dir: Path, file_path: Path, info: dict) -> Path:
    artist = (info.get("artist") or info.get("uploader") or "Unknown Artist").strip()
    raw_title = info.get("track") or info.get("title") or "Unknown Title"
    title = clean_title(raw_title)

    audio = MP3(file_path, ID3=EasyID3)
    try:
        audio.add_tags()
    except Exception:
        pass
    audio["artist"] = artist
    audio["title"] = title
    audio.save()

    output_path = choose_output_path(download_dir, artist, title)
    file_path.rename(output_path)
    return output_path
