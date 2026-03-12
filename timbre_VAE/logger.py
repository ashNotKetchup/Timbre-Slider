# -------------------------------
# Debug LOGGING
# -------------------------------

import json
import os
import threading
from datetime import datetime


def log(msg):
    """Send debug log to Max API or print if unavailable."""
    # if debug:
    try:
        print(msg)
    except Exception:
        print(msg)


class RequestLogger:
    """Accumulates timestamped request/response log entries in memory.

    Call ``log(request, response)`` for every HTTP exchange.
    Call ``save_to_file(path)`` to persist the full log, or
    ``open_save_dialogue()`` to let the user choose a destination via a
    native file-save dialog.
    """

    def __init__(self):
        self._entries: list[dict] = []

    # ---- recording ----
    def log(self, request: dict, response: dict) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "request": request,
            "response": response,
        }
        self._entries.append(entry)
        print(f"[log] #{len(self._entries)} {request.get('type', '?')} → {response.get('type', '?')}")

    # ---- export helpers ----
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self._entries, indent=indent, default=str)

    def save_to_file(self, path: str) -> str:
        """Write the full log to *path* and return the absolute path."""
        with open(path, "w") as f:
            f.write(self.to_json())
        print(f"[log] Saved {len(self._entries)} entries → {path}")
        return os.path.abspath(path)

    def open_save_dialogue(self) -> str | None:
        """Open a native file-save dialog and return the chosen path.

        Uses the native save dialog for the current OS (no extra deps):
        - macOS: ``osascript``
        - Windows: PowerShell ``SaveFileDialog``
        - Linux: ``zenity`` or ``kdialog``
        Falls back to auto-saving to ``./logs_<timestamp>.json``.
        """
        import subprocess, sys

        result: list[str | None] = [None]
        default_name = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        def _try_macos() -> str | None:
            script = (
                'tell application "System Events"\n'
                '  activate\n'
                'end tell\n'
                f'set f to POSIX path of (choose file name with prompt '
                f'"Save request/response logs" default name "{default_name}")\n'
                'return f'
            )
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=120,
            )
            return proc.stdout.strip() or None

        def _try_windows() -> str | None:
            ps_script = (
                'Add-Type -AssemblyName System.Windows.Forms; '
                '$d = New-Object System.Windows.Forms.SaveFileDialog; '
                "$d.Title = 'Save request/response logs'; "
                f"$d.FileName = '{default_name}'; "
                "$d.Filter = 'JSON files (*.json)|*.json|Text files (*.txt)|*.txt|All files (*.*)|*.*'; "
                'if ($d.ShowDialog() -eq "OK") { $d.FileName }'
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=120,
            )
            return proc.stdout.strip() or None

        def _try_linux() -> str | None:
            # Try zenity first (GTK), then kdialog (KDE)
            for cmd in [
                ["zenity", "--file-selection", "--save",
                 "--confirm-overwrite", "--title=Save request/response logs",
                 f"--filename={default_name}"],
                ["kdialog", "--getsavefilename", os.getcwd(),
                 "JSON files (*.json);;All files (*)"],
            ]:
                try:
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=120,
                    )
                    path = proc.stdout.strip()
                    if proc.returncode == 0 and path:
                        return path
                except FileNotFoundError:
                    continue
            return None

        def _dialogue():
            path = None
            try:
                if sys.platform == "darwin":
                    path = _try_macos()
                elif sys.platform == "win32":
                    path = _try_windows()
                else:
                    path = _try_linux()
            except Exception as e:
                print(f"[log] Save dialog error: {e}")

            if path:
                if not path.endswith(".json"):
                    path += ".json"
                self.save_to_file(path)
                result[0] = path
            else:
                # Auto-save fallback
                fallback = os.path.join(os.getcwd(), default_name)
                self.save_to_file(fallback)
                result[0] = fallback
                print(f"[log] Auto-saved → {fallback}")

        t = threading.Thread(target=_dialogue, daemon=True)
        t.start()
        t.join(timeout=120)
        return result[0]

    @property
    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()
        print("[log] Cleared.")