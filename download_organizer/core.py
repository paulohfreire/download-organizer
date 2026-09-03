"""Application seam for configuring and manually running the Organizer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import fnmatch
import json
from pathlib import Path
import shutil
from typing import Any


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

    def validate(self) -> None:
        if not self.downloads_folder.strip():
            raise ValueError("Downloads folder is required")
        if not self.unsorted_folder.strip():
            raise ValueError("Unsorted folder is required")
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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrganizerConfig":
        return cls(
            downloads_folder=data.get("downloads_folder", ""),
            unsorted_folder=data.get("unsorted_folder", ""),
            allowed_locations=list(data.get("allowed_locations", [])),
            rules=[Rule(**item) for item in data.get("rules", [])],
        )


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


class Organizer:
    """High-level behavior seam used by user interfaces and tests."""

    def __init__(self, config: OrganizerConfig, config_store: JsonConfigStore | None = None):
        self.config = config
        self.config_store = config_store

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

    def organize_now(self) -> list[dict[str, str]]:
        self.config.validate()
        downloads = Path(self.config.downloads_folder)
        results: list[dict[str, str]] = []
        if not downloads.exists():
            return results
        for source in sorted(downloads.iterdir()):
            if not source.is_file() or source.is_symlink() or source.suffix.lower() == ".lnk":
                continue
            rule = next((candidate for candidate in self.config.rules if candidate.matches(source.name)), None)
            destination_folder = Path(rule.destination if rule else self.config.unsorted_folder)
            destination_folder.mkdir(parents=True, exist_ok=True)
            destination = _available_path(destination_folder / source.name)
            shutil.move(str(source), str(destination))
            results.append(
                {
                    "source": str(source),
                    "destination": str(destination),
                    "reason": rule.name if rule else "Unsorted",
                }
            )
        return results


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
