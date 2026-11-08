"""'Start with Windows' via the per-user Run registry key."""
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "LimiTools"
LEGACY_VALUE_NAMES = ("RolimonsAdPoster",)  # before the rename


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    script = Path(__file__).resolve().parent.parent / "gui.py"
    return f'"{pythonw if pythonw.exists() else sys.executable}" "{script}" --minimized'


def is_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except (ImportError, OSError):
        return False


def migrate_legacy() -> None:
    """Moves a "Start with Windows" entry from the app's old name to the new one (it points at the old
    RoliAdPoster.exe, which the installer removes). Does nothing elsewhere or when there's none."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            found = False
            for name in LEGACY_VALUE_NAMES:
                try:
                    winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    continue
                winreg.DeleteValue(key, name)
                found = True
            if found:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
    except (ImportError, OSError):
        pass


def set_enabled(enabled: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
