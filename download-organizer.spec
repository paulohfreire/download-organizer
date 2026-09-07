# PyInstaller one-file build for the Windows desktop application.
#
# Build from the repository root with:
#   py -m PyInstaller --clean --noconfirm download-organizer.spec
#
# The explicit watchdog imports are needed because watchdog selects its
# platform observer dynamically at runtime.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path(SPECPATH)
hiddenimports = [
    "watchdog.events",
    "watchdog.observers",
    "watchdog.observers.api",
    "watchdog.observers.read_directory_changes",
]

a = Analysis(
    [str(project_root / "download_organizer" / "windows_entrypoint.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=collect_data_files("watchdog"),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DownloadOrganizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
