# Download Organizer

Download Organizer safely places completed Downloads into user-defined folders while preserving move history and recovery options. The desktop interface is a Windows application.

## Build the Windows application locally

On Windows with Python 3.11 or newer:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
python -m pip install . --no-deps
python -m PyInstaller --clean --noconfirm download-organizer.spec
```

The standalone executable is written to `dist\DownloadOrganizer.exe`. Launch it with:

```powershell
.\dist\DownloadOrganizer.exe
```

The build is self-contained and does not require Python on the target Windows machine. The build process does not launch the GUI; run the executable when you want to use it.

## Configuration and move history

The application stores its files under `%APPDATA%\DownloadOrganizer\`:

- `config.json` contains the Downloads, Unsorted, rule, scan interval, allowed-location, and start-on-login settings.
- `history.json` contains move, skip, failure, retry, and undo history.

These files are created or updated when configuration is saved. Use the desktop **Export config** and **Import config** controls to transfer settings; move history remains local to the machine.
