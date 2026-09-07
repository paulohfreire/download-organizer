"""Command-line fallback for the Organizer."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .core import JsonConfigStore, JsonHistoryStore, Organizer


def default_config_path() -> Path:
    app_data = os.environ.get("APPDATA") or (Path.home() / ".config")
    return Path(app_data) / "DownloadOrganizer" / "config.json"


def main() -> int:
    parser = argparse.ArgumentParser(prog="download-organizer")
    parser.add_argument("organize", nargs="?", choices=["organize", "retry-failed"], default="organize")
    parser.add_argument("--config", type=Path, default=default_config_path())
    args = parser.parse_args()
    store = JsonConfigStore(args.config)
    organizer = Organizer(store.load(), store, JsonHistoryStore(args.config.with_name("history.json")))
    action = organizer.retry_failed(force=True) if args.organize == "retry-failed" else organizer.organize_now()
    for result in action:
        print(f"{result['source']} -> {result['destination']} ({result['reason']})")
    return 0
