from __future__ import annotations

import json
import socket
import threading
import time
import tkinter as tk


class Lab:
    def __init__(self) -> None:
        self.root = tk.Tk(); self.root.title("Mini 2 SE — laboratory simulator")
        self.values = {"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "vertical": 0.0}
        self.last_packet = 0.0; self.seq = -1; self.lock = threading.Lock()
        self.labels = {}
        for name in self.values:
            label = tk.Label(self.root, text=f"{name.upper()}: 0.00", font=("Consolas", 18), width=30)
            label.pack(padx=20, pady=5); self.labels[name] = label
        self.status = tk.Label(self.root, text="WAITING FOR PC", font=("Consolas", 14)); self.status.pack(pady=10)
        threading.Thread(target=self.server, daemon=True).start(); self.root.after(100, self.tick)

    def server(self) -> None:
        server = socket.socket(); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); server.bind(("127.0.0.1", 8766)); server.listen(1)
        while True:
            client, _ = server.accept()
            with client:
                buffer = b""
                while True:
                    chunk = client.recv(4096)
                    if not chunk: break
                    buffer += chunk
                    while b"\n" in buffer:
                        raw, buffer = buffer.split(b"\n", 1)
                        try:
                            packet = json.loads(raw); output = packet.get("output", {})
                            with self.lock:
                                self.values = {key: float(output.get(key, 0.0)) for key in self.values}; self.last_packet = time.monotonic(); self.seq = packet.get("seq", self.seq)
                        except (ValueError, TypeError):
                            pass

    def tick(self) -> None:
        with self.lock:
            stale = time.monotonic() - self.last_packet > 0.4
            values = {key: 0.0 for key in self.values} if stale else dict(self.values)
            seq = self.seq
        for key, value in values.items(): self.labels[key].configure(text=f"{key.upper()}: {value:+.3f}")
        self.status.configure(text="FAILSAFE: NEUTRAL" if stale else f"LINK OK  seq={seq}")
        self.root.after(100, self.tick)


if __name__ == "__main__":
    Lab().root.mainloop()
