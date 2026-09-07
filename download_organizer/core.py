"""Application seam for configuring and manually running the Organizer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import fnmatch
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable


@dataclass
class Rule:
    """An ordered condition and fixed Destination for a Download."""

    name: str
    extension: str = ""
    filename_pattern: str = "*"
    destination: str = ""

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Rule name is required")
        if not self.destination.strip():
            raise ValueError("Rule destination is required")
        if not self.filename_pattern:
            raise ValueError("Rule filename pattern is required")

    def matches(self, filename: str) -> bool:
        extension = Path(filename).suffix.lower()
        wanted_extension = self.extension.strip().lower()
        if wanted_extension and not wanted_extension.startswith("."):
            wanted_extension = f".{wanted_extension}"
        return (not wanted_extension or extension == wanted_extension) and fnmatch.fnmatchcase(
            filename.lower(), self.filename_pattern.lower()
        )


@dataclass
class OrganizerConfig:
    downloads_folder: str = ""
    unsorted_folder: str = ""
    allowed_locations: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    scan_interval_seconds: int = 10

    def validate(self) -> None:
        if not self.downloads_folder.strip():
            raise ValueError("Downloads folder is required")
        if not self.unsorted_folder.strip():
            raise ValueError("Unsorted folder is required")
        if self.scan_interval_seconds <= 0:
            raise ValueError("Scan interval must be positive")
        for rule in self.rules:
            rule.validate()
        for destination in [self.unsorted_folder, *[r.destination for r in self.rules]]:
            if self.allowed_locations and not _within_allowed(Path(destination), self.allowed_locations):
                raise ValueError(f"Destination is outside allowed locations: {destination}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "downloads_folder": self.downloads_folder,
            "unsorted_folder": self.unsorted_folder,
            "allowed_locations": self.allowed_locations,
            "rules": [asdict(rule) for rule in self.rules],
            "scan_interval_seconds": self.scan_interval_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrganizerConfig":
        return cls(
            downloads_folder=data.get("downloads_folder", ""),
            unsorted_folder=data.get("unsorted_folder", ""),
            allowed_locations=list(data.get("allowed_locations", [])),
            rules=[Rule(**item) for item in data.get("rules", [])],
            scan_interval_seconds=int(data.get("scan_interval_seconds", 10)),
        )


@dataclass
class ActivityRecord:
    kind: str
    timestamp: str
    source: str
    destination: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "ActivityRecord":
        return cls(data["kind"], data["timestamp"], data["source"], data["destination"], data["reason"])


class JsonConfigStore:
    """Persistence adapter shared by the CLI and desktop shell."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> OrganizerConfig:
        if not self.path.exists():
            return OrganizerConfig()
        config = OrganizerConfig.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        config.validate()
        return config

    def save(self, config: OrganizerConfig) -> None:
        config.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")


class JsonHistoryStore:
    """Persistence adapter for Move history, intentionally separate from config export."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[ActivityRecord]:
        if not self.path.exists():
            return []
        return [ActivityRecord.from_dict(item) for item in json.loads(self.path.read_text(encoding="utf-8"))]

    def save(self, records: list[ActivityRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([record.to_dict() for record in records], indent=2), encoding="utf-8")


class WindowsNotifier:
    """Best-effort Windows session notification; callers can inject a test notifier."""

    def __call__(self, message: str) -> None:
        try:
            subprocess.Popen(["msg.exe", "*", "/TIME:10", message], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


class Organizer:
    """High-level behavior seam used by user interfaces and tests."""

    def __init__(
        self,
        config: OrganizerConfig,
        config_store: JsonConfigStore | None = None,
        history_store: JsonHistoryStore | None = None,
        clock: Callable[[], datetime] | None = None,
        notifier: Callable[[str], None] | None = None,
    ):
        self.config = config
        self.config_store = config_store
        self.history_store = history_store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.history = history_store.load() if history_store else []
        self._failed: dict[str, tuple[str, int, datetime]] = self._restore_failed()
        self.notifications: list[str] = []
        self._last_notification: datetime | None = None
        self.notifier = notifier or (lambda _message: None)
        self._stability: dict[str, tuple[int, int, bool]] = {}

    def _restore_failed(self) -> dict[str, tuple[str, int, datetime]]:
        failed: dict[str, tuple[str, int, datetime]] = {}
        for record in self.history:
            if record.kind == "failure":
                attempt = failed.get(record.source, (record.reason, 0, self.clock()))[1] + 1
                timestamp = datetime.fromisoformat(record.timestamp)
                failed[record.source] = (record.reason, attempt, timestamp + timedelta(seconds=10 * attempt))
            elif record.kind in {"move", "undo"}:
                failed.pop(record.source, None)
        return failed

    def save_configuration(self) -> None:
        if self.config_store is None:
            raise ValueError("No configuration store configured")
        self.config_store.save(self.config)

    def add_rule(self, rule: Rule) -> None:
        rule.validate()
        self.config.rules.append(rule)

    def update_rule(self, index: int, rule: Rule) -> None:
        rule.validate()
        self.config.rules[index] = rule

    def move_rule(self, index: int, new_index: int) -> None:
        rule = self.config.rules.pop(index)
        self.config.rules.insert(new_index, rule)

    def _record(self, kind: str, source: Path, destination: Path | str, reason: str) -> ActivityRecord:
        record = ActivityRecord(kind, self.clock().isoformat(), str(source), str(destination), reason)
        self.history.append(record)
        if self.history_store:
            self.history_store.save(self.history)
        return record

    def _notify_failure(self, message: str) -> None:
        now = self.clock()
        if self._last_notification is None or now - self._last_notification >= timedelta(minutes=1):
            self.notifications.append(message)
            self._last_notification = now
            self.notifier(message)

    def _move_source(self, source: Path, destination_folder: Path, reason: str) -> dict[str, str]:
        destination = destination_folder / source.name
        try:
            destination_folder.mkdir(parents=True, exist_ok=True)
            destination = _available_path(destination)
            shutil.move(str(source), str(destination))
        except OSError as error:
            attempt = self._failed.get(str(source), (reason, 0, self.clock()))[1] + 1
            self._failed[str(source)] = (reason, attempt, self.clock() + timedelta(seconds=10 * attempt))
            self._record("failure", source, destination, str(error))
            self._notify_failure(f"Could not move {source.name}: {error}")
            return {"source": str(source), "destination": str(destination), "reason": str(error), "status": "failure"}
        self._failed.pop(str(source), None)
        self._record("move", source, destination, reason)
        return {"source": str(source), "destination": str(destination), "reason": reason, "status": "moved"}

    def organize_now(self) -> list[dict[str, str]]:
        self.config.validate()
        downloads = Path(self.config.downloads_folder)
        results: list[dict[str, str]] = []
        if not downloads.exists():
            return results
        for source in sorted(downloads.iterdir()):
            if source.is_dir():
                self._record("skip", source, "", "Directory")
                results.append({"source": str(source), "destination": "", "reason": "Directory", "status": "skip"})
                continue
            if source.is_symlink():
                self._record("skip", source, "", "Symlink")
                results.append({"source": str(source), "destination": "", "reason": "Symlink", "status": "skip"})
                continue
            if not source.is_file() or source.suffix.lower() == ".lnk":
                self._record("skip", source, "", "Shortcut or non-file")
                results.append({"source": str(source), "destination": "", "reason": "Shortcut or non-file", "status": "skip"})
                continue
            failed = self._failed.get(str(source))
            if failed and self.clock() < failed[2]:
                results.append({"source": str(source), "destination": "", "reason": "Retry backoff", "status": "deferred"})
                continue
            rule = next((candidate for candidate in self.config.rules if candidate.matches(source.name)), None)
            destination_folder = Path(rule.destination if rule else self.config.unsorted_folder)
            results.append(self._move_source(source, destination_folder, rule.name if rule else "Unsorted"))
        return results

    def initial_scan(self, confirmed: bool) -> list[dict[str, str]]:
        """Process existing files only after explicit first-run confirmation."""
        if not confirmed:
            return []
        return self.scan_once()

    def on_filesystem_event(self, path: Path) -> list[dict[str, str]]:
        """Handle one Windows filesystem event without moving an incomplete Download."""
        return self.scan_once([Path(path)], is_rescan=False)

    def rescan(self) -> list[dict[str, str]]:
        """Rescan the configured folder to recover missed filesystem events."""
        return self.scan_once(is_rescan=True)

    def scan_once(self, paths: list[Path] | None = None, is_rescan: bool = True) -> list[dict[str, str]]:
        self.config.validate()
        downloads = Path(self.config.downloads_folder)
        candidates = paths if paths is not None else (list(downloads.iterdir()) if downloads.exists() else [])
        results: list[dict[str, str]] = []
        for source in sorted({Path(path) for path in candidates}):
            if not source.exists() or source.parent != downloads:
                continue
            if source.is_dir() or source.is_symlink() or not source.is_file() or source.suffix.lower() == ".lnk":
                continue
            stat = source.stat()
            current = (stat.st_size, stat.st_mtime_ns)
            previous = self._stability.get(str(source))
            self._stability[str(source)] = (*current, is_rescan)
            if previous is None or previous[:2] != current:
                results.append({"source": str(source), "destination": "", "reason": "Awaiting Completion", "status": "waiting"})
                continue
            if not is_rescan:
                results.append({"source": str(source), "destination": "", "reason": "Awaiting rescan confirmation", "status": "waiting"})
                continue
            self._stability.pop(str(source), None)
            failed = self._failed.get(str(source))
            if failed and self.clock() < failed[2]:
                results.append({"source": str(source), "destination": "", "reason": "Retry backoff", "status": "deferred"})
                continue
            rule = next((candidate for candidate in self.config.rules if candidate.matches(source.name)), None)
            results.append(self._move_source(source, Path(rule.destination if rule else self.config.unsorted_folder), rule.name if rule else "Unsorted"))
        return results

    def retry_failed(self, force: bool = False) -> list[dict[str, str]]:
        """Retry failures whose backoff has elapsed, or all failures when forced manually."""
        now = self.clock()
        results: list[dict[str, str]] = []
        for source_name, (reason, _attempt, next_retry) in list(self._failed.items()):
            if not force and now < next_retry:
                continue
            source = Path(source_name)
            destination = next((Path(rule.destination) for rule in self.config.rules if rule.matches(source.name)), Path(self.config.unsorted_folder))
            if source.exists() and source.is_file() and not source.is_symlink():
                results.append(self._move_source(source, destination, reason))
        return results

    def undo(self, history_index: int) -> ActivityRecord:
        record = self.history[history_index]
        if record.kind != "move":
            raise ValueError("Only successful Moves can be undone")
        source = Path(record.source)
        destination = Path(record.destination)
        if source.exists():
            return self._record("undo-failure", source, destination, "Original path is occupied")
        if not destination.exists():
            return self._record("undo-failure", source, destination, "Moved file is missing")
        source.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(destination), str(source))
        except OSError as error:
            return self._record("undo-failure", source, destination, str(error))
        return self._record("undo", destination, source, "Move undone")

    def clear_history(self) -> None:
        self.history.clear()
        if self.history_store:
            self.history_store.save(self.history)


def _available_path(candidate: Path) -> Path:
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    number = 1
    while True:
        alternate = candidate.with_name(f"{stem} ({number}){suffix}")
        if not alternate.exists():
            return alternate
        number += 1


def _within_allowed(path: Path, allowed_locations: list[str]) -> bool:
    resolved = path.expanduser().resolve()
    return any(resolved == root.resolve() or root.resolve() in resolved.parents for root in map(Path, allowed_locations))
