from pathlib import Path

import pytest

from download_organizer.core import JsonConfigStore, Organizer, OrganizerConfig, Rule


def make_organizer(tmp_path: Path) -> Organizer:
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    config = OrganizerConfig(
        downloads_folder=str(downloads),
        unsorted_folder=str(tmp_path / "Unsorted"),
        allowed_locations=[str(tmp_path)],
    )
    return Organizer(config, JsonConfigStore(tmp_path / "config.json"))


def test_manual_run_moves_matching_and_unmatched_files(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    organizer.add_rule(Rule("PDF files", ".pdf", "*report*", str(tmp_path / "Documents")))
    organizer.save_configuration()
    downloads = Path(organizer.config.downloads_folder)
    (downloads / "annual-report.PDF").write_text("report")
    (downloads / "photo.jpg").write_text("photo")

    results = organizer.organize_now()

    assert (tmp_path / "Documents" / "annual-report.PDF").exists()
    assert (tmp_path / "Unsorted" / "photo.jpg").exists()
    assert {item["reason"] for item in results} == {"PDF files", "Unsorted"}


def test_first_matching_rule_wins_and_rules_can_be_reordered(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    first = Rule("First", ".txt", "*", str(tmp_path / "First"))
    second = Rule("Second", ".txt", "*", str(tmp_path / "Second"))
    organizer.add_rule(first)
    organizer.add_rule(second)
    organizer.move_rule(1, 0)
    organizer.save_configuration()
    (Path(organizer.config.downloads_folder) / "note.txt").write_text("note")

    organizer.organize_now()

    assert (tmp_path / "Second" / "note.txt").exists()


def test_invalid_rule_cannot_be_saved(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    with pytest.raises(ValueError, match="destination"):
        organizer.add_rule(Rule("Missing destination", ".pdf", "*", ""))


def test_configuration_round_trips_for_cli_and_desktop(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    organizer.add_rule(Rule("PDF files", ".pdf", "*.pdf", str(tmp_path / "PDF")))
    organizer.save_configuration()

    loaded = JsonConfigStore(tmp_path / "config.json").load()

    assert loaded.downloads_folder == organizer.config.downloads_folder
    assert loaded.rules[0] == organizer.config.rules[0]


def test_folders_and_symlinks_are_ignored(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    downloads = Path(organizer.config.downloads_folder)
    (downloads / "nested").mkdir()
    (downloads / "ignored.txt").write_text("ignored")
    try:
        (downloads / "link.txt").symlink_to(downloads / "ignored.txt")
    except (OSError, NotImplementedError):
        pass

    results = organizer.organize_now()

    assert len(results) == 1
    assert (downloads / "nested").is_dir()


def test_windows_shortcuts_are_ignored(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    downloads = Path(organizer.config.downloads_folder)
    (downloads / "shortcut.lnk").write_text("shortcut")

    results = organizer.organize_now()

    assert results == []
    assert (downloads / "shortcut.lnk").exists()
