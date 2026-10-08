"""Bounded local TCP bridge with ACK health and monotonic round-trip timing."""
from __future__ import annotations

import json
import select
import secrets
import socket
import time
import uuid
from typing import Any
from windows.signed_frames import VERSION, decode_signed, encode_signed, pairing_code


class JsonLineServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        if host != "127.0.0.1" or type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Mostek może nasłuchiwać tylko na IPv4 localhost")
        self.host, self.port = host, port
        self.pairing_token = secrets.token_hex(32)
        self.pairing_code = pairing_code(self.pairing_token)
        self.client_nonce = ""
        self.server = None
        self.client = None
        self.session = ""
        self.buffer = bytearray()
        self.pending: dict[int, float] = {}
        self.accepted_at = self.last_ack = 0.0
        self.rtt_ms = self.rtt_max = self.rtt_total = 0.0
        self.rtt_count = 0
        self.remote: dict[str, Any] = {}
        self.reason = "wyłączony"

    @property
    def connected(self) -> bool:
        return self.client is not None

    @property
    def healthy(self) -> bool:
        return self.connected and self.last_ack > 0 and time.monotonic() - self.last_ack < 0.3

    @property
    def average_rtt(self) -> float:
        return self.rtt_total / self.rtt_count if self.rtt_count else 0.0

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(1)
            sock.setblocking(False)
        except OSError:
            sock.close()
            raise
        self.server = sock
        self.reason = "oczekiwanie na Android"

    def disconnect(self, reason: str):
        if self.client:
            self.client.close()
        self.client = None
        self.pending.clear()
        self.buffer.clear()
        self.last_ack = 0.0
        self.remote = {}
        self.client_nonce = ""
        self.reason = reason

    def accept_once(self) -> bool:
        if not self.server:
            return False
        try:
            sock, _ = self.server.accept()
        except BlockingIOError:
            return False
        except OSError:
            self.reason = "błąd przyjmowania TCP"
            return False
        if self.client is not None:
            sock.close()  # A second local process must not replace an active session.
            return False
        self.disconnect("nowa sesja")
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(0.003)
        self.client = sock
        self.session = uuid.uuid4().hex
        self.accepted_at = time.monotonic()
        self.rtt_ms = self.rtt_max = self.rtt_total = 0.0
        self.rtt_count = 0
        return True

    def poll(self):
        if not self.client:
            return
        try:
            for _ in range(4):
                if not select.select([self.client], [], [], 0)[0]:
                    break
                chunk = self.client.recv(8192)
                if not chunk:
                    self.disconnect("Android zamknął TCP")
                    return
                self.buffer.extend(chunk)
                if len(self.buffer) > 32768:
                    raise ValueError("odpowiedź przekracza limit")
                while b"\n" in self.buffer:
                    line, _, rest = self.buffer.partition(b"\n")
                    self.buffer = bytearray(rest)
                    ack = decode_signed(line, self.pairing_token)
                    if not self.client_nonce:
                        nonce = ack.get("clientNonce")
                        if ack.get("type") != "hello" or type(ack.get("version")) is not int or ack["version"] != VERSION or not isinstance(nonce, str) or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
                            raise ValueError("Nieprawidłowe uwierzytelnienie telefonu")
                        self.client_nonce = nonce
                        continue
                    if (ack.get("type") != "ack" or type(ack.get("version")) is not int or ack["version"] != VERSION
                            or ack.get("sessionId") != self.session or ack.get("clientNonce") != self.client_nonce
                            or ack.get("flightControl") is not False):
                        raise ValueError("niezgodny protokół ACK")
                    seq = ack.get("seq")
                    if type(seq) is not int:
                        raise ValueError("Nieprawidłowa sekwencja ACK")
                    if seq not in self.pending:
                        continue
                    now = time.monotonic()
                    rtt = (now - self.pending.pop(seq)) * 1000
                    if rtt >= 300:
                        self.disconnect("ACK spóźnione ≥300 ms: neutral")
                        return
                    self.last_ack = now
                    self.rtt_ms = rtt
                    self.rtt_total += rtt
                    self.rtt_max = max(self.rtt_max, rtt)
                    self.rtt_count += 1
                    self.remote = ack
            if time.monotonic() - (self.last_ack or self.accepted_at) > 0.3:
                self.disconnect("watchdog ACK 300 ms: wyjście neutralne")
        except (OSError, ValueError, TypeError, AttributeError, RecursionError):
            self.disconnect("błąd odpowiedzi Androida")

    def send(self, packet: dict[str, Any]) -> bool:
        if not self.client or not self.client_nonce:
            return False
        frame = dict(packet, version=VERSION, sessionId=self.session, clientNonce=self.client_nonce, type="control")
        frame.setdefault("inputConnected", False)
        frame.setdefault("emergency", False)
        try:
            payload = encode_signed(frame, self.pairing_token)
            if len(payload) > 8192:
                raise ValueError("Za duży pakiet")
            self.client.sendall(payload)
            self.pending[frame["seq"]] = time.monotonic()
            if len(self.pending) > 64:
                self.disconnect("brak odpowiedzi ACK")
            return self.connected
        except (OSError, ValueError):
            self.disconnect("nie udało się wysłać pakietu")
            return False

    def close(self):
        self.disconnect("wyłączony")
        if self.server:
            self.server.close()
        self.server = None
