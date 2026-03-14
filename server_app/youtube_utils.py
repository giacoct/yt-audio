"""YouTube URL validation and playlist expansion helpers."""

from __future__ import annotations

from typing import List
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL


def is_youtube_url(raw_url: str) -> bool:
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return False
    return parsed.netloc.endswith("youtube.com") or parsed.netloc.endswith("youtu.be")


def canonical_video_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if "youtu.be" in parsed.netloc:
        video_id = parsed.path.strip("/")
        return f"https://www.youtube.com/watch?v={video_id}"

    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return f"https://www.youtube.com/watch?v={qs['v'][0]}"
    return raw_url


def expand_to_video_urls(raw_url: str) -> List[str]:
    ydl_opts = {"quiet": True, "extract_flat": True, "skip_download": True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(raw_url, download=False)

    entries = info.get("entries") if isinstance(info, dict) else None
    if not entries:
        return [canonical_video_url(raw_url)]

    urls = []
    for entry in entries:
        if not entry:
            continue
        entry_url = entry.get("url") or entry.get("webpage_url")
        if not entry_url:
            continue
        if not entry_url.startswith("http"):
            entry_url = f"https://www.youtube.com/watch?v={entry_url}"
        urls.append(canonical_video_url(entry_url))

    return list(dict.fromkeys(urls)) or [canonical_video_url(raw_url)]
