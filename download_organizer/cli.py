"""Command-line fallback for the Organizer."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .core import JsonConfigStore, Organizer


def default_config_path() -> Path:
    app_data = os.environ.get("APPDATA") or (Path.home() / ".config")
    return Path(app_data) / "DownloadOrganizer" / "config.json"


def main() -> int:
    parser = argparse.ArgumentParser(prog="download-organizer")
    parser.add_argument("organize", nargs="?", choices=["organize"], default="organize")
    parser.add_argument("--config", type=Path, default=default_config_path())
    args = parser.parse_args()
    store = JsonConfigStore(args.config)
    organizer = Organizer(store.load(), store)
    for result in organizer.organize_now():
        print(f"{result['source']} -> {result['destination']} ({result['reason']})")
    return 0
