"""Read-only DJI Fly screen viewer. Never sends touch, flight or USB commands."""
import os
from pathlib import Path
from queue import Empty, Full, Queue
import shutil
import subprocess
import threading


class ScreenViewer:
    def __init__(self, app_dir: Path):
        self.app_dir = app_dir
        self.process = None
        self.events = Queue(maxsize=128)
        self.gate = threading.Lock()
        self.closed = False

    def executable(self) -> Path:
        candidates = [self.app_dir / "video" / "scrcpy-win64-v5.0" / "scrcpy.exe",
                      self.app_dir / "dist" / "video" / "scrcpy-win64-v5.0" / "scrcpy.exe"]
        if shutil.which("scrcpy"):
            candidates.append(Path(shutil.which("scrcpy")))
        for path in candidates:
            if path.is_file(): return path
        raise RuntimeError("Brak odtwarzacza w folderze video. Zachowaj folder video obok EXE.")

    @staticmethod
    def arguments(executable: Path, serial: str) -> list[str]:
        return [str(executable), "--serial=" + serial, "--no-control", "--no-clipboard-autosync", "--no-audio",
                "--max-size=1280", "--max-fps=30", "--video-bit-rate=4M", "--print-fps",
                "--window-title=G29 / DJI Fly - SCREEN MIRROR - READ ONLY", "--window-width=960", "--window-height=540"]

    def start(self, adb_path: str, serial: str) -> str:
        with self.gate:
            if self.closed:
                raise RuntimeError("Kokpit jest już zamknięty")
            return self._start(adb_path, serial)

    def _start(self, adb_path: str, serial: str) -> str:
        if self.process and self.process.poll() is None:
            return "Podgląd już działa. Otwórz DJI Fly na telefonie."
        executable = self.executable()
        environment = dict(os.environ, ADB=adb_path)
        process = subprocess.Popen(self.arguments(executable, serial), cwd=executable.parent, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.process = process
        def collect():
            with process.stdout:
                for line in process.stdout:
                    try: self.events.put_nowait(line.strip())
                    except Full: pass
            code = process.wait()
            try: self.events.put_nowait(f"VIDEO zakończone / kod {code}")
            except Full: pass
        threading.Thread(target=collect, name="video-status", daemon=True).start()
        return "Podgląd uruchomiony w osobnym oknie. Otwórz DJI Fly na telefonie. Bez sterowania i bez nagrywania."

    def poll(self) -> list[str]:
        events = []
        try:
            while len(events) < 8: events.append(self.events.get_nowait())
        except Empty: pass
        return events

    def stop(self):
        with self.gate:
            self._stop()

    def _stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()  # only this cockpit's viewer, never all scrcpy/adb processes

    def close(self):
        with self.gate:
            self.closed = True
            self._stop()
