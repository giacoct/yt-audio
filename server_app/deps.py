"""Dependency and runtime checks."""

from __future__ import annotations

import shutil
import subprocess
import sys

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


def ensure_ffmpeg() -> bool:
    if shutil.which("ffmpeg") is not None:
        return True

    print("[setup] FFmpeg not found in PATH.")
    print("[setup] Install FFmpeg and make sure `ffmpeg` is available from the terminal.")
    print("[setup] Ubuntu/Debian: sudo apt install ffmpeg")
    print("[setup] macOS (brew): brew install ffmpeg")
    print("[setup] Windows (choco): choco install ffmpeg")
    return False
