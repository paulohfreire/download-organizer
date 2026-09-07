"""Windows filesystem event adapter for the Organizer seam."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


class WindowsFileWatcher:
    """Bridge watchdog events to Organizer.on_filesystem_event.

    The dependency is optional at import time so the core and CLI remain usable in
    environments that only run deterministic tests.
    """

    def __init__(self, folder: Path, on_path: Callable[[Path], None]):
        self.folder = Path(folder)
        self.on_path = on_path
        self._observer = None

    def start(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError as error:
            raise RuntimeError("Install watchdog to enable Windows filesystem events") from error

        callback = self.on_path

        class Handler(FileSystemEventHandler):
            def _forward(self, event):
                if not event.is_directory:
                    callback(Path(event.src_path))

            def on_created(self, event):
                self._forward(event)

            def on_modified(self, event):
                self._forward(event)

            def on_moved(self, event):
                if not event.is_directory:
                    callback(Path(event.dest_path))

        self._observer = Observer()
        self._observer.schedule(Handler(), str(self.folder), recursive=False)
        self._observer.start()

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
