"""ADB discovery and read-only diagnostics. Subprocess arguments never use a shell."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE = "com.example.g29dronecontrol"


def locate_adb(custom: str = "") -> str:
    candidates = [custom, shutil.which("adb") or ""]
    app_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    candidates.extend(str(app_dir / folder / "scrcpy-win64-v5.0" / "adb.exe") for folder in ("video", "dist/video"))
    for key in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        if os.environ.get(key):
            candidates.append(str(Path(os.environ[key]) / "platform-tools" / "adb.exe"))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(str(Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk" / "platform-tools" / "adb.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Brak adb.exe. Wskaż platform-tools/adb.exe z Android SDK.")


class AdbLink:
    def __init__(self, path: str = ""):
        self.path = locate_adb(path)

    def run(self, args: list[str], serial: str = "", timeout: int = 12) -> str:
        command = [self.path] + (["-s", serial] if serial else []) + args
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip()[:1000])
        return result.stdout.strip()

    def devices(self) -> list[dict[str, str]]:
        found = []
        for line in self.run(["devices", "-l"]).splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and not line.startswith("*"):
                found.append({"serial": parts[0], "state": parts[1], "description": " ".join(parts[2:])})
        return found

    def setup(self, serial: str, port: int, pairing_token: str):
        from windows.signed_frames import key_bytes
        key_bytes(pairing_token)
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Nieprawidłowy port mostka")
        if self.run(["get-state"], serial) != "device":
            raise RuntimeError("Telefon nie jest autoryzowany lub jest offline.")
        self.run(["reverse", f"tcp:{port}", f"tcp:{port}"], serial)
        installed = self.run(["shell", "pm", "path", PACKAGE], serial)
        if not installed.startswith("package:"):
            raise RuntimeError("Kanał ADB gotowy. Najpierw kliknij ZAINSTALUJ APK.")
        try:
            self.run(["shell", "am", "start", "-n", f"{PACKAGE}/.MainActivity", "--es", "pairingToken", pairing_token, "--ei", "port", str(port)], serial)
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(str(error).replace(pairing_token, "[klucz sesji ukryty]")) from None
        return "Sesja przygotowana. Porównaj kod z Windows i na telefonie 0.6 kliknij Potwierdź komputer i połącz. SDK i połączenie nie zostały uruchomione automatycznie."

    def install(self, serial: str, apk: Path):
        if not apk.is_file():
            raise RuntimeError("Brak pliku G29Bridge.apk obok programu.")
        return self.run(["install", "-r", str(apk)], serial, timeout=90)

    def connect_wifi(self, address: str):
        self.validate_address(address)
        return self.run(["connect", address])

    @staticmethod
    def validate_address(address: str):
        if not re.fullmatch(r"[a-zA-Z0-9.\-\[\]:]+:\d{1,5}", address) or not 1 <= int(address.rsplit(":", 1)[1]) <= 65535:
            raise RuntimeError("Wpisz adres i port debugowania, np. 192.168.1.10:37123.")

    def pair_wifi(self, address: str, code: str):
        self.validate_address(address)
        if not re.fullmatch(r"\d{6}", code):
            raise RuntimeError("Kod parowania powinien mieć 6 cyfr.")
        return self.run(["pair", address, code], timeout=30)

    def diagnostics(self, serial: str) -> str:
        usb = self.run(["shell", "dumpsys", "usb"], serial)
        try:
            fly = self.run(["shell", "pm", "path", "dji.go.v5"], serial)
        except RuntimeError:
            fly = ""
        return "DJI Fly zainstalowany: " + ("TAK" if fly else "NIE / niewykryty") + "\n\nDUMPSYS USB (nie potwierdza radiowego połączenia z dronem):\n" + usb[:24000]
