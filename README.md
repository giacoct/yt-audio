# YouTube Audio Downloader (Chrome Extension + Python Server)

## What this project does

- Chrome extension button sends the current YouTube URL to a local Flask server.
- Server handles single videos and playlists.
- Downloads are FIFO (one at a time), deduplicated, and converted to MP3.
- Extension icon badge reflects status: queued, downloading, completed, failed.

## Project layout

```text
extension/
├── manifest.json
├── background.js
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
server.py
downloads/
```

## Requirements

- Python 3.9+
- FFmpeg installed and available as `ffmpeg`
- Chrome/Chromium browser

Python packages are auto-checked at startup (`flask`, `yt-dlp`, `mutagen`).
If auto-install fails, follow the printed instructions.

## Run the server

```bash
python server.py
```

Optional env vars:

- `AUDIO_QUALITY` (default `192`)
- `DOWNLOAD_DIR` (default `downloads`)

## Install extension in Chrome

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder

## Usage

1. Start `python server.py`
2. Open a YouTube video or playlist tab
3. Click the extension toolbar icon
4. Badge shows progress:
   - `Q` queued
   - `↓` downloading (animated color pulse)
   - `✓` completed
   - `!` failed

Downloaded files are renamed to:

```text
Artist - Title.mp3
```

with cleaned title metadata and ID3 artist/title tags.
