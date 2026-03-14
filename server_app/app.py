"""Flask app factory and routes."""

from __future__ import annotations

from dataclasses import asdict

from flask import Flask, jsonify, request

from .config import ServerSettings, load_settings, save_settings
from .downloader import AudioDownloader
from .queue_manager import DownloadQueueManager
from .youtube_utils import expand_to_video_urls, is_youtube_url


def create_app() -> tuple[Flask, DownloadQueueManager, ServerSettings]:
    settings = load_settings()
    downloader = AudioDownloader(settings)
    queue_manager = DownloadQueueManager(downloader)

    app = Flask(__name__)

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

        return jsonify(queue_manager.enqueue_many(source_url, expanded_urls))

    @app.route("/status", methods=["GET"])
    def status_endpoint():
        source_url = (request.args.get("url") or "").strip()
        if not source_url:
            return jsonify({"error": "Missing url query parameter."}), 400
        return jsonify({"url": source_url, "status": queue_manager.get_status(source_url)})

    @app.route("/settings", methods=["GET", "POST"])
    def settings_endpoint():
        nonlocal settings
        if request.method == "GET":
            return jsonify(asdict(settings))

        payload = request.get_json(silent=True) or {}
        updated = ServerSettings(
            host=str(payload.get("host", settings.host)).strip() or settings.host,
            port=int(payload.get("port", settings.port)),
            audio_quality=str(payload.get("audio_quality", settings.audio_quality)).strip() or settings.audio_quality,
            download_dir=str(payload.get("download_dir", settings.download_dir)).strip() or settings.download_dir,
            retries=int(payload.get("retries", settings.retries)),
            fragment_retries=int(payload.get("fragment_retries", settings.fragment_retries)),
        )

        settings = updated
        save_settings(settings)

        # Refresh downloader behavior immediately.
        queue_manager.downloader.settings = settings

        return jsonify({"saved": True, **asdict(settings)})

    @app.route("/progress", methods=["GET"])
    def progress_endpoint():
        return jsonify(queue_manager.get_overall_progress())

    @app.route("/health", methods=["GET"])
    def health_endpoint():
        return jsonify({"ok": True})

    return app, queue_manager, settings
