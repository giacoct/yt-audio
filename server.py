"""Flask + yt-dlp audio downloader queue for YouTube URLs."""

from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import parse_qs, urlparse

# Dependency bootstrap: try import, attempt auto-install, and provide fix instructions on failure.
REQUIRED_PY_PACKAGES = {
    "flask": "flask",
    "yt_dlp": "yt-dlp",
    "mutagen": "mutagen",
}


def ensure_python_dependencies() -> bool:
    missing = []
    for module_name, pip_name in REQUIRED_PY_PACKAGES.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append((module_name, pip_name))

    if not missing:
        return True

    print("[setup] Missing dependencies detected. Attempting auto-install...")
    for _, pip_name in missing:
        cmd = [sys.executable, "-m", "pip", "install", pip_name]
        print(f"[setup] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"[setup] Failed to install '{pip_name}'.")
            print("[setup] Install manually with:")
            print(f"    {sys.executable} -m pip install {' '.join(p for _, p in missing)}")
            return False
    return True


if not ensure_python_dependencies():
    raise SystemExit(1)

from flask import Flask, jsonify, request
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from yt_dlp import YoutubeDL

# Configurable quality for extracted MP3 (yt-dlp FFmpegExtractAudio preferredquality).
AUDIO_QUALITY = os.environ.get("AUDIO_QUALITY", "192")
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "downloads")).resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

if shutil.which("ffmpeg") is None:
    print("[setup] FFmpeg not found in PATH.")
    print("[setup] Install FFmpeg and make sure `ffmpeg` is available from the terminal.")
    print("[setup] Ubuntu/Debian: sudo apt install ffmpeg")
    print("[setup] macOS (brew): brew install ffmpeg")
    print("[setup] Windows (choco): choco install ffmpeg")
    raise SystemExit(1)

app = Flask(__name__)

# Queue and state tracking for one-at-a-time FIFO downloads.
download_queue: "queue.Queue[str]" = queue.Queue()
queued_or_active: Set[str] = set()
item_status: Dict[str, str] = {}
item_errors: Dict[str, str] = {}

# A source URL can map to one or many item URLs (playlist expands to many).
source_to_items: Dict[str, Set[str]] = defaultdict(set)
item_to_sources: Dict[str, Set[str]] = defaultdict(set)

state_lock = threading.Lock()


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
    """Expand a YouTube URL into individual video URLs (playlist supported)."""
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

    # Preserve order but remove duplicates.
    deduped = list(dict.fromkeys(urls))
    return deduped or [canonical_video_url(raw_url)]


def clean_title(raw_title: str) -> str:
    title = raw_title or "Unknown Title"
    for pattern in NOISE_PATTERNS:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)

    # Remove extra separators and squeeze whitespace.
    title = re.sub(r"[_|]+", " ", title)
    title = re.sub(r"\s+-\s+", " - ", title)
    title = re.sub(r"\s{2,}", " ", title).strip(" -_[]()")
    return title or "Unknown Title"


def safe_filename(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", text).strip() or "Unknown"


def aggregate_source_status(source_url: str) -> str:
    with state_lock:
        items = source_to_items.get(source_url)
        if not items:
            return "idle"
        statuses = [item_status.get(item, "idle") for item in items]

    if any(status == "downloading" for status in statuses):
        return "downloading"
    if any(status == "queued" for status in statuses):
        return "queued"
    if statuses and all(status == "completed" for status in statuses):
        return "completed"
    if statuses and all(status in {"completed", "failed"} for status in statuses) and any(
        status == "failed" for status in statuses
    ):
        return "failed"
    return "idle"


def choose_output_path(artist: str, title: str) -> Path:
    base_name = safe_filename(f"{artist} - {title}")
    candidate = DOWNLOAD_DIR / f"{base_name}.mp3"
    counter = 1
    while candidate.exists():
        candidate = DOWNLOAD_DIR / f"{base_name} ({counter}).mp3"
        counter += 1
    return candidate


def write_metadata_and_rename(file_path: Path, info: dict) -> Path:
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

    output_path = choose_output_path(artist, title)
    file_path.rename(output_path)
    return output_path


def download_audio(video_url: str) -> Path:
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "ignoreerrors": False,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": AUDIO_QUALITY,
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

    mp3_path = DOWNLOAD_DIR / f"{video_id}.mp3"
    if not mp3_path.exists():
        found = sorted(DOWNLOAD_DIR.glob(f"{video_id}*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not found:
            raise FileNotFoundError("Expected mp3 output file not found after download.")
        mp3_path = found[0]

    return write_metadata_and_rename(mp3_path, info)


def mark_item_status(item_url: str, status: str, error: str | None = None) -> None:
    with state_lock:
        item_status[item_url] = status
        if error:
            item_errors[item_url] = error


def worker_loop() -> None:
    while True:
        video_url = download_queue.get()
        mark_item_status(video_url, "downloading")
        print(f"[downloading] {video_url}")
        try:
            output_path = download_audio(video_url)
            mark_item_status(video_url, "completed")
            print(f"[completed] {video_url} -> {output_path}")
        except Exception as exc:  # Broad catch for robust queue continuation.
            mark_item_status(video_url, "failed", str(exc))
            print(f"[failed] {video_url}: {exc}")
        finally:
            with state_lock:
                queued_or_active.discard(video_url)
            download_queue.task_done()
            time.sleep(0.1)


@app.route("/url", methods=["POST"])
def enqueue_endpoint():
    payload = request.get_json(silent=True) or {}
    source_url = (payload.get("url") or "").strip()
    if not source_url:
        return jsonify({"error": "Missing 'url' field."}), 400
    if not is_youtube_url(source_url):
        return jsonify({"error": "Only YouTube URLs are supported."}), 400

    try:
        expanded_urls = expand_to_video_urls(source_url)
    except Exception as exc:
        return jsonify({"error": f"Unable to read URL info: {exc}"}), 400

    queued = []
    skipped_duplicates = []

    with state_lock:
        for item_url in expanded_urls:
            source_to_items[source_url].add(item_url)
            item_to_sources[item_url].add(source_url)

            if item_url in queued_or_active:
                skipped_duplicates.append(item_url)
                continue

            queued_or_active.add(item_url)
            item_status[item_url] = "queued"
            download_queue.put(item_url)
            queued.append(item_url)
            print(f"[queued] {item_url}")

    return jsonify(
        {
            "source_url": source_url,
            "queued": queued,
            "duplicates": skipped_duplicates,
            "total_items": len(expanded_urls),
            "source_status": aggregate_source_status(source_url),
        }
    )


@app.route("/status", methods=["GET"])
def status_endpoint():
    source_url = (request.args.get("url") or "").strip()
    if not source_url:
        return jsonify({"error": "Missing url query parameter."}), 400

    if source_url in item_status:
        status = item_status[source_url]
    else:
        status = aggregate_source_status(source_url)

    return jsonify({"url": source_url, "status": status})


@app.route("/health", methods=["GET"])
def health_endpoint():
    return jsonify({"ok": True})


def start_worker() -> None:
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()


if __name__ == "__main__":
    print(f"[setup] Download directory: {DOWNLOAD_DIR}")
    print(f"[setup] MP3 quality: {AUDIO_QUALITY} kbps")
    start_worker()
    app.run(host="127.0.0.1", port=5000, debug=False)
