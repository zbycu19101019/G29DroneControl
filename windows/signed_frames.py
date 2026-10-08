"""Protocol v2: authenticate exact UTF-8 payloads, not re-serialized JSON."""
import hashlib
import hmac
import json
import re

VERSION = 2


def key_bytes(token: str) -> bytes:
    if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{64}", token):
        raise ValueError("Nieprawidłowy klucz sesji")
    return bytes.fromhex(token)


def pairing_code(token: str) -> str:
    return hashlib.sha256(key_bytes(token)).hexdigest()[:8].upper()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Powtórzony klucz JSON")
        result[key] = value
    return result


def _load(value):
    return json.loads(value, object_pairs_hook=_unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nieskończona liczba JSON")))


def encode_signed(packet: dict, token: str) -> bytes:
    body = json.dumps(packet, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    mac = hmac.new(key_bytes(token), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return (json.dumps({"version": VERSION, "payload": body, "mac": mac}, separators=(",", ":")) + "\n").encode("utf-8")


def decode_signed(frame: bytes | str, token: str) -> dict:
    envelope = _load(frame)
    if not isinstance(envelope, dict) or set(envelope) != {"version", "payload", "mac"}:
        raise ValueError("Nieprawidłowa koperta")
    if type(envelope["version"]) is not int or envelope["version"] != VERSION:
        raise ValueError("Wymagana aktualizacja obu aplikacji do protokołu v2")
    body, mac = envelope["payload"], envelope["mac"]
    if not isinstance(body, str) or len(body.encode("utf-8")) > 16000:
        raise ValueError("Za duży podpisany pakiet")
    if not isinstance(mac, str) or not re.fullmatch(r"[a-f0-9]{64}", mac):
        raise ValueError("Brak prawidłowego podpisu")
    expected = hmac.new(key_bytes(token), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("Nieprawidłowy podpis pakietu")
    value = _load(body)
    if not isinstance(value, dict):
        raise ValueError("Pakiet musi być obiektem")
    return value
