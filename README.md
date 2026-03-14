# YouTube Audio Downloader (Chrome Extension + Python Server)

## What this project does

- Chrome extension toolbar button sends the current YouTube URL to a local Flask server.
- Supports single videos and playlists.
- FIFO queue (one active download), deduplication, and MP3 conversion.
- Extension icon shows a single aggregated circular progress ring across all downloads.
- Extension **Settings page** lets you edit all server runtime settings.

## Project layout

```text
extension/
├── manifest.json
├── background.js
├── options.html
├── options.css
├── options.js
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
server.py
server_app/
├── app.py
├── config.py
├── deps.py
├── downloader.py
├── metadata.py
├── queue_manager.py
└── youtube_utils.py
settings.json
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

The server reads/writes settings from `settings.json`.

## Configure from extension settings UI

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** and select `extension/`
4. Open extension **Details** → **Extension options**
5. Edit and save settings:
   - `host`
   - `port`
   - `audio_quality`
   - `download_dir`
   - `retries`
   - `fragment_retries`

These are sent to `POST /settings` and persisted in `settings.json`.

## Usage

1. Start `python server.py`
2. Open a YouTube video or playlist tab
3. Click the extension toolbar icon
4. Extension icon shows one circular progress ring for all downloads combined.
   - Blue: downloading in progress
   - Grey: queued but not started
   - Green: all finished successfully
   - Red: finished with one or more failures

Downloaded files are renamed to `Artist - Title.mp3` with cleaned titles and ID3 tags.
