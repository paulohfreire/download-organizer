"""Windows login startup integration."""

from __future__ import annotations

import sys


def startup_command() -> str:
    """Return the command used by Windows to launch the desktop application.

    A source checkout needs the module invocation, while a PyInstaller build
    must launch the executable directly.  In a frozen process ``sys.executable``
    points at the bundled application and does not accept ``-m`` arguments.
    """

    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m download_organizer.desktop'


class WindowsStartup:
    """Manage the user's Run entry without affecting non-Windows environments."""

    value_name = "DownloadOrganizer"

    def __init__(self, command: str):
        self.command = command

    def set_enabled(self, enabled: bool) -> None:
        if sys.platform != "win32":
            return
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, self.value_name, 0, winreg.REG_SZ, self.command)
            else:
                try:
                    winreg.DeleteValue(key, self.value_name)
                except FileNotFoundError:
                    pass
