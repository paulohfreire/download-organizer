"""Windows login startup integration."""

from __future__ import annotations

import sys


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
