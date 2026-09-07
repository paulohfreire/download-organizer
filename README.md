# Download Organizer

Download Organizer is a Windows desktop application that watches one Downloads folder, waits for files to finish downloading, and places them into predictable destinations using ordered Rules. It keeps Move history so decisions can be reviewed and safely undone.

## What it does

- Organizes regular files by extension and case-insensitive filename wildcards.
- Sends files with no matching Rule to `Unsorted`.
- Waits for a file's size and modified time to remain stable before automatic intake.
- Watches for new files and periodically rescans when an event is missed.
- Never overwrites an existing file; collisions become `filename (1).ext`, `filename (2).ext`, and so on.
- Leaves failed Moves in Downloads for retry and shows them in activity history.
- Supports Undo when the original path is still safe to restore.
- Ignores folders, Windows shortcuts (`.lnk`), symlinks, and other non-regular files.

## Downloading the Windows application

There is currently no installer or signed public release. The project produces a portable, windowed `DownloadOrganizer.exe` through GitHub Actions.

For a development or maintainer build:

1. Open the repository's **Actions** tab.
2. Open a successful **Windows desktop build** run.
3. Download the `DownloadOrganizer-windows` artifact.
4. Extract `DownloadOrganizer.exe` to a user-owned folder and launch it.

The CI artifact is temporary and may require repository access. A stable GitHub Release will replace this distribution path when one is published.

## First-time setup

1. Launch `DownloadOrganizer.exe`.
2. Choose the Downloads folder and an `Unsorted` folder.
3. Add ordered Rules. Each Rule can specify an extension, a filename wildcard, and a fixed Destination.
4. Add every intended Destination to **Allowed locations**. Destinations outside these safety boundaries cannot be saved.
5. Set the scan interval and, optionally, **Start on login**.
6. Select **Save**.

The application creates missing Destination folders automatically when they are inside the configured allowed locations.

## Organizing files

The desktop controls have distinct purposes:

- **Initial scan**: after confirmation, observes existing Downloads files. Use **Rescan** after the files have had a stable observation to process them.
- **Start watching**: listens for new filesystem events and schedules periodic rescans.
- **Rescan**: checks the configured Downloads folder and processes files that have remained stable across two observations.
- **Organize now**: immediately processes the current regular files, without waiting for automatic completion detection.

Use the Rules list to add, edit, delete, or move Rules up and down. The first matching Rule wins. Use the activity filter to review Move, skip, failure, or Undo records, and **Clear history** to remove local activity history.

## Command-line fallback

With the project installed in an active Python environment, the CLI supports manual organization and forced retries:

```powershell
download-organizer organize
download-organizer retry-failed
download-organizer organize --config C:\path\to\config.json
```

The CLI and desktop application use the same configuration and history format. The `--config` option is useful for testing or for running a separate configuration.

## Safety and recovery

Download Organizer is deliberately conservative:

- A Destination collision never replaces the existing file.
- A failed Move leaves the source Download in place and remains eligible for retry.
- Every Move, skip, failure, and Undo result records a timestamp, source, destination, and reason.
- Undo refuses to overwrite a newer file that now occupies the original Downloads path.
- Move history remains until you explicitly clear it.

## Configuration and history

The default files are stored under `%APPDATA%\DownloadOrganizer\`:

- `config.json` stores folders, Rules, allowed locations, scan interval, and startup preference.
- `history.json` stores Move, skip, failure, retry, and Undo activity.

Use **Export config** and **Import config** to move settings between machines. Move history is intentionally not included in exported configuration and remains local.

## Building locally

Builds require Windows and Python 3.11 or newer. The repository pins the build inputs used by CI:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
python -m pip install . --no-deps
python -m PyInstaller --clean --noconfirm download-organizer.spec
```

The standalone executable is written to `dist\DownloadOrganizer.exe`. It contains the application runtime and does not require Python on the target machine. The build itself does not launch the GUI.

Run the tests with:

```powershell
python -m pytest
```

## Troubleshooting

- **The application will not save configuration**: verify that every Destination is inside one of the configured Allowed locations.
- **A file is waiting**: automatic intake needs two observations with unchanged size and modified time. Use **Rescan** again after the download completes.
- **A file is not moved**: check the activity history for a skip, failure, or retry-backoff record. Folders, shortcuts, symlinks, and non-regular files are intentionally ignored.
- **Filesystem watching is unavailable**: install the project dependencies in the active Python environment, or use **Rescan** and **Organize now** while troubleshooting.
- **The artifact is unavailable**: CI artifacts are temporary and access-controlled until a public GitHub Release is published.
