"""FIFO queue manager for one-at-a-time downloads."""

from __future__ import annotations

import queue
import threading
import time
from collections import defaultdict
from typing import Dict, Set

from .downloader import AudioDownloader


class DownloadQueueManager:
    def __init__(self, downloader: AudioDownloader):
        self.downloader = downloader
        self.download_queue: "queue.Queue[str]" = queue.Queue()
        self.queued_or_active: Set[str] = set()
        self.item_status: Dict[str, str] = {}
        self.item_errors: Dict[str, str] = {}
        self.source_to_items: Dict[str, Set[str]] = defaultdict(set)
        self.state_lock = threading.Lock()

    def aggregate_source_status(self, source_url: str) -> str:
        with self.state_lock:
            items = self.source_to_items.get(source_url)
            if not items:
                return "idle"
            statuses = [self.item_status.get(item, "idle") for item in items]

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

    def get_overall_progress(self) -> dict:
        """Return aggregated progress across all known downloads."""
        with self.state_lock:
            statuses = list(self.item_status.values())

        total = len(statuses)
        queued = sum(1 for status in statuses if status == "queued")
        downloading = sum(1 for status in statuses if status == "downloading")
        completed = sum(1 for status in statuses if status == "completed")
        failed = sum(1 for status in statuses if status == "failed")

        # Failed entries are considered finished for progress accounting.
        finished = completed + failed
        percent = int((finished / total) * 100) if total else 0

        overall_status = "idle"
        if total > 0:
            if downloading > 0:
                overall_status = "downloading"
            elif queued > 0:
                overall_status = "queued"
            elif finished == total and failed == 0:
                overall_status = "completed"
            elif finished == total and failed > 0:
                overall_status = "failed"

        return {
            "status": overall_status,
            "total": total,
            "queued": queued,
            "downloading": downloading,
            "completed": completed,
            "failed": failed,
            "percent": percent,
        }

    def get_status(self, source_url: str) -> str:
        with self.state_lock:
            if source_url in self.item_status:
                return self.item_status[source_url]
        return self.aggregate_source_status(source_url)

    def enqueue_many(self, source_url: str, item_urls: list[str]) -> dict:
        queued = []
        duplicates = []
        with self.state_lock:
            for item_url in item_urls:
                self.source_to_items[source_url].add(item_url)
                if item_url in self.queued_or_active:
                    duplicates.append(item_url)
                    continue
                self.queued_or_active.add(item_url)
                self.item_status[item_url] = "queued"
                self.download_queue.put(item_url)
                queued.append(item_url)
                print(f"[queued] {item_url}")

        return {
            "source_url": source_url,
            "queued": queued,
            "duplicates": duplicates,
            "total_items": len(item_urls),
            "source_status": self.aggregate_source_status(source_url),
        }

    def mark_item_status(self, item_url: str, status: str, error: str | None = None) -> None:
        with self.state_lock:
            self.item_status[item_url] = status
            if error:
                self.item_errors[item_url] = error

    def worker_loop(self) -> None:
        while True:
            video_url = self.download_queue.get()
            self.mark_item_status(video_url, "downloading")
            print(f"[downloading] {video_url}")
            try:
                output_path = self.downloader.download_audio(video_url)
                self.mark_item_status(video_url, "completed")
                print(f"[completed] {video_url} -> {output_path}")
            except Exception as exc:
                self.mark_item_status(video_url, "failed", str(exc))
                print(f"[failed] {video_url}: {exc}")
            finally:
                with self.state_lock:
                    self.queued_or_active.discard(video_url)
                self.download_queue.task_done()
                time.sleep(0.1)

    def start_worker(self) -> None:
        thread = threading.Thread(target=self.worker_loop, daemon=True)
        thread.start()
