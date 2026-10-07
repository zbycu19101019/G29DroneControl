"""Line-delimited JSON transport for PC -> Android via adb reverse."""
from __future__ import annotations
import json, socket, threading, time
from typing import Any

class JsonLineServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host, self.port = host, port
        self._server: socket.socket | None = None
        self._client: socket.socket | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port)); self._server.listen(1); self._server.settimeout(0.2)
        print(f"PC transport: {self.host}:{self.port}; Android: adb reverse tcp:{self.port} tcp:{self.port}")

    def accept_once(self) -> None:
        if not self._server: return
        try: client, address = self._server.accept()
        except socket.timeout: return
        with self._lock:
            if self._client: self._client.close()
            self._client = client
        print(f"Android połączony: {address}")

    def send(self, packet: dict[str, Any]) -> bool:
        payload = (json.dumps(packet, separators=(",", ":")) + "\n").encode()
        with self._lock:
            if not self._client: return False
            try: self._client.sendall(payload); return True
            except OSError: self._client = None; return False

    def close(self) -> None:
        with self._lock:
            if self._client: self._client.close()
            if self._server: self._server.close()
            self._client = self._server = None
