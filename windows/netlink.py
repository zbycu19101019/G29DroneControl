"""Local JSON Lines TCP server for an Android client behind adb reverse."""
from __future__ import annotations

import json
import socket
from typing import Any


class JsonLineServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host, self.port = host, port
        self.server: socket.socket | None = None
        self.client: socket.socket | None = None

    @property
    def connected(self) -> bool:
        return self.client is not None

    def start(self) -> None:
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(1)
        self.server.setblocking(False)

    def accept_once(self) -> bool:
        if self.server is None:
            return False
        try:
            client, _ = self.server.accept()
        except BlockingIOError:
            return False
        if self.client is not None:
            self.client.close()
        client.settimeout(0.005)
        self.client = client
        return True

    def send(self, packet: dict[str, Any]) -> bool:
        if self.client is None:
            return False
        try:
            self.client.sendall((json.dumps(packet, separators=(",", ":")) + "\n").encode("utf-8"))
            return True
        except (OSError, TimeoutError):
            self.client.close()
            self.client = None
            return False

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
        if self.server is not None:
            self.server.close()
            self.server = None
