"""Real-time directory file system event watcher trigger using watchdog."""

import asyncio
import os
from typing import Any, Awaitable, Callable, Dict, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from neo.triggers.base import BaseTrigger
from neo.core.models import TriggerConfig
from neo.core.context import RunContext


class _NeoFileHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, on_event: Callable[[Dict[str, Any]], Awaitable[None]], patterns: list):
        self.loop = loop
        self.on_event = on_event
        self.patterns = [p.lower() for p in patterns] if patterns else []

    def _matches(self, path: str) -> bool:
        if not self.patterns:
            return True
        ext = os.path.splitext(path)[1].lower()
        return any(ext == p or p == "*" for p in self.patterns)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._matches(event.src_path):
            self._dispatch("created", event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._matches(event.src_path):
            self._dispatch("modified", event.src_path)

    def _dispatch(self, event_type: str, file_path: str) -> None:
        filename = os.path.basename(file_path)
        payload = {
            "trigger_type": "file_watch",
            "event": event_type,
            "path": file_path,
            "filename": filename,
            "extension": os.path.splitext(filename)[1],
            "size_bytes": os.path.getsize(file_path) if os.path.exists(file_path) else 0
        }
        asyncio.run_coroutine_threadsafe(self.on_event(payload), self.loop)


class FileWatchTrigger(BaseTrigger):
    """Watches directories in real time for file creation and modification."""

    def __init__(self, config: TriggerConfig, templater=None):
        super().__init__(config, templater)
        self.observer: Optional[Observer] = None

    async def start(self, on_event: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        self.is_running = True
        context = RunContext()
        cfg = self.templater.resolve(self.config.model_dump(), context)

        watch_path = cfg.get("path") or cfg.get("directory")
        if not watch_path:
            raise ValueError("File watch trigger requires 'path'.")

        watch_path = os.path.abspath(os.path.expanduser(watch_path))
        os.makedirs(watch_path, exist_ok=True)

        patterns = cfg.get("patterns") or cfg.get("extensions") or []
        if isinstance(patterns, str):
            patterns = [p.strip() for p in patterns.split(",")]

        loop = asyncio.get_running_loop()
        event_handler = _NeoFileHandler(loop, on_event, patterns)

        self.observer = Observer()
        self.observer.schedule(event_handler, watch_path, recursive=cfg.get("recursive", False))
        self.observer.start()

    async def stop(self) -> None:
        self.is_running = False
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2.0)
