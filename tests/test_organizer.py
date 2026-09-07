from pathlib import Path

import pytest

from datetime import datetime, timezone

from download_organizer.core import JsonConfigStore, JsonHistoryStore, Organizer, OrganizerConfig, Rule


def make_organizer(tmp_path: Path) -> Organizer:
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    config = OrganizerConfig(
        downloads_folder=str(downloads),
        unsorted_folder=str(tmp_path / "Unsorted"),
        allowed_locations=[str(tmp_path)],
    )
    return Organizer(config, JsonConfigStore(tmp_path / "config.json"), JsonHistoryStore(tmp_path / "history.json"))


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

    assert sum(item["status"] == "moved" for item in results) == 1
    assert sum(item["status"] == "skip" for item in results) >= 1
    assert (downloads / "nested").is_dir()


def test_windows_shortcuts_are_ignored(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    downloads = Path(organizer.config.downloads_folder)
    (downloads / "shortcut.lnk").write_text("shortcut")

    results = organizer.organize_now()

    assert results[0]["status"] == "skip"
    assert (downloads / "shortcut.lnk").exists()


def test_collisions_are_suffixed_and_history_persists(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    destination = tmp_path / "Documents"
    organizer.add_rule(Rule("Text", ".txt", "*", str(destination)))
    (destination).mkdir()
    (destination / "note.txt").write_text("old")
    source = Path(organizer.config.downloads_folder) / "note.txt"
    source.write_text("new")

    result = organizer.organize_now()[0]
    loaded = JsonHistoryStore(tmp_path / "history.json").load()

    assert Path(result["destination"]).name == "note (1).txt"
    assert loaded[0].kind == "move"


def test_failed_move_can_be_retried_and_notifies_once_per_minute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    current = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    organizer = make_organizer(tmp_path)
    organizer.clock = lambda: current[0]
    source = Path(organizer.config.downloads_folder) / "file.txt"
    source.write_text("data")
    import download_organizer.core as core
    real_move = core.shutil.move
    monkeypatch.setattr(core.shutil, "move", lambda *_args: (_ for _ in ()).throw(OSError("locked")))

    result = organizer.organize_now()[0]
    assert result["status"] == "failure"
    assert source.exists()
    assert len(organizer.notifications) == 1
    current[0] = current[0].replace(second=30)
    organizer.retry_failed(force=True)
    assert len(organizer.notifications) == 1
    monkeypatch.setattr(core.shutil, "move", real_move)


def test_failed_move_backoff_survives_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    organizer = make_organizer(tmp_path)
    source = Path(organizer.config.downloads_folder) / "file.txt"
    source.write_text("data")
    import download_organizer.core as core
    monkeypatch.setattr(core.shutil, "move", lambda *_args: (_ for _ in ()).throw(OSError("locked")))
    organizer.organize_now()

    reloaded = Organizer(
        organizer.config,
        organizer.config_store,
        organizer.history_store,
        clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert reloaded.organize_now()[0]["status"] == "deferred"


def test_skips_are_persisted_in_history(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    downloads = Path(organizer.config.downloads_folder)
    (downloads / "shortcut.lnk").write_text("shortcut")

    organizer.organize_now()

    assert organizer.history[0].kind == "skip"
    organizer.clear_history()
    assert organizer.history == []


def test_automatic_intake_waits_for_two_stable_observations(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    organizer.add_rule(Rule("Text", ".txt", "*", str(tmp_path / "Documents")))
    source = Path(organizer.config.downloads_folder) / "file.txt"
    source.write_text("data")

    first = organizer.on_filesystem_event(source)
    second = organizer.rescan()

    assert first[0]["status"] == "waiting"
    assert second[0]["status"] == "moved"
    assert not source.exists()


def test_automatic_intake_does_not_move_changing_file(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    source = Path(organizer.config.downloads_folder) / "file.txt"
    source.write_text("one")

    organizer.on_filesystem_event(source)
    source.write_text("two")
    result = organizer.rescan()[0]

    assert result["status"] == "waiting"
    assert source.exists()


def test_repeated_events_require_rescan_confirmation(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    source = Path(organizer.config.downloads_folder) / "file.txt"
    source.write_text("data")

    organizer.on_filesystem_event(source)
    repeated_event = organizer.on_filesystem_event(source)
    confirmed = organizer.rescan()

    assert repeated_event[0]["status"] == "waiting"
    assert confirmed[0]["status"] == "moved"


def test_initial_scan_requires_confirmation_and_rescan_deduplicates(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    source = Path(organizer.config.downloads_folder) / "file.txt"
    source.write_text("data")

    assert organizer.initial_scan(False) == []
    assert source.exists()
    organizer.initial_scan(True)
    assert organizer.rescan()[0]["status"] == "moved"
    assert organizer.rescan() == []


def test_undo_refuses_occupied_original_path(tmp_path: Path) -> None:
    organizer = make_organizer(tmp_path)
    source = Path(organizer.config.downloads_folder) / "file.txt"
    source.write_text("data")
    organizer.organize_now()
    destination = Path(organizer.history[0].destination)
    source.write_text("new occupant")

    result = organizer.undo(0)

    assert result.kind == "undo-failure"
    assert source.read_text() == "new occupant"
    assert destination.exists()
