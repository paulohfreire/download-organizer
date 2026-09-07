from pathlib import Path

from download_organizer.cli import default_config_path
from download_organizer import startup
from download_organizer.core import JsonConfigStore, OrganizerConfig


PROJECT_ROOT = Path(__file__).parents[1]


def test_frozen_startup_command_launches_executable(monkeypatch) -> None:
    monkeypatch.setattr(startup.sys, "executable", r"C:\Program Files\Download Organizer\DownloadOrganizer.exe")
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)

    assert startup.startup_command() == r'"C:\Program Files\Download Organizer\DownloadOrganizer.exe"'


def test_source_startup_command_preserves_module_invocation(monkeypatch) -> None:
    monkeypatch.setattr(startup.sys, "executable", r"C:\Python311\python.exe")
    monkeypatch.setattr(startup.sys, "frozen", False, raising=False)

    assert startup.startup_command() == r'"C:\Python311\python.exe" -m download_organizer.desktop'


def test_desktop_spec_is_windowed_and_bundles_watchdog() -> None:
    spec = (PROJECT_ROOT / "download-organizer.spec").read_text(encoding="utf-8")

    assert '"download_organizer" / "windows_entrypoint.py"' in spec
    assert 'name="DownloadOrganizer"' in spec
    assert "console=False" in spec
    assert '"watchdog.observers.read_directory_changes"' in spec


def test_windows_build_is_pinned_and_launch_smoke_tested() -> None:
    requirements = (PROJECT_ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")

    assert "pyinstaller==" in requirements
    assert "watchdog==" in requirements
    assert "python-version: \"3.11.9\"" in workflow
    assert "Start-Process -FilePath $artifact" in workflow
    assert "Expected a one-file build" in workflow


def test_default_config_path_uses_appdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert default_config_path() == tmp_path / "DownloadOrganizer" / "config.json"


def test_config_store_creates_appdata_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    config_path = default_config_path()
    config = OrganizerConfig(
        downloads_folder=str(tmp_path / "Downloads"),
        unsorted_folder=str(tmp_path / "Unsorted"),
    )

    JsonConfigStore(config_path).save(config)

    assert config_path.is_file()
