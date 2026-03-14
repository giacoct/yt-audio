"""Entry point for YouTube audio downloader server."""

from __future__ import annotations

from server_app.deps import ensure_ffmpeg, ensure_python_dependencies


def main() -> None:
    if not ensure_python_dependencies():
        raise SystemExit(1)

    # Delay imports until after dependency checks/install attempts.
    from server_app.app import create_app

    if not ensure_ffmpeg():
        raise SystemExit(1)

    app, queue_manager, settings = create_app()
    queue_manager.start_worker()

    print(f"[setup] Download directory: {settings.download_dir}")
    print(f"[setup] MP3 quality: {settings.audio_quality} kbps")
    app.run(host=settings.host, port=settings.port, debug=False)


if __name__ == "__main__":
    main()
