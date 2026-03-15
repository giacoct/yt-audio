"""Audio metadata cleanup and deterministic file naming."""

from __future__ import annotations

import re
from pathlib import Path

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

BRACKETED_SEGMENT_RE = re.compile(r"\s*[\[(]([^\])()]*)[\])]")
FEATURED_ARTIST_RE = re.compile(r"\b(feat\.?|ft\.?|featuring)\b", re.IGNORECASE)
NOISE_PHRASE_RE = re.compile(
    r"\b(official(\s+music)?\s+video|official\s+audio|lyrics?|lyric\s+video|"
    r"visuali[sz]er|video\s+musicale\s+ufficiale|testo|audio|4k|hd|hq)\b",
    re.IGNORECASE,
)
INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|]')
SEPARATOR_RE = re.compile(r"\s*[-–|_:]+\s*")
MULTISPACE_RE = re.compile(r"\s{2,}")


def _remove_non_featured_bracketed_segments(title: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if FEATURED_ARTIST_RE.search(inner):
            return f" ({inner})"
        return " "

    return BRACKETED_SEGMENT_RE.sub(replacer, title)


def clean_title(raw_title: str) -> str:
    title = (raw_title or "Unknown Title").strip()
    title = _remove_non_featured_bracketed_segments(title)
    title = NOISE_PHRASE_RE.sub(" ", title)
    title = title.replace("_", " ")
    title = SEPARATOR_RE.sub(" - ", title)
    title = MULTISPACE_RE.sub(" ", title).strip(" -_[]()")
    return title or "Unknown Title"


def safe_filename(text: str) -> str:
    return INVALID_FILENAME_CHARS_RE.sub("", text).strip() or "Unknown"


def choose_output_path(download_dir: Path, title: str) -> Path:
    base_name = safe_filename(title)
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

    output_path = choose_output_path(download_dir, title)
    file_path.rename(output_path)
    return output_path
