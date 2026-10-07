"""Deterministic G29 -> abstract drone-channel mapping. No DJI calls here."""
from __future__ import annotations
import math
from typing import Any

PROFILES = {
    "NORMAL": {"yaw": 1.0, "pitch": 1.0, "roll": 1.0, "vertical": 1.0},
    "SMOOTH": {"yaw": 0.6, "pitch": 0.7, "roll": 0.7, "vertical": 0.7},
    "CINEMATIC": {"yaw": 0.3, "pitch": 0.4, "roll": 0.4, "vertical": 0.4},
    "AGRESYWNY": {"yaw": 1.0, "pitch": 1.0, "roll": 1.0, "vertical": 1.0},
    "GTA STYLE": {"yaw": 0.8, "pitch": 0.85, "roll": 0.8, "vertical": 0.9},
}

def expo(value: float, amount: float) -> float:
    amount = max(0.05, min(1.0, amount))
    return math.copysign(abs(value) ** (1.0 / amount), value)

def map_state(state: dict[str, Any], config: dict[str, Any], profile: str = "NORMAL") -> dict[str, float]:
    profile = profile.upper().replace("_", " ")
    p = PROFILES.get(profile, PROFILES["NORMAL"])
    limit = float(config.get("outputLimit", 1.0))
    # Pedals are exposed as signed axes by many SDL/DirectInput profiles;
    # convert them to 0..1 before applying the requested mapping.
    throttle = (float(state.get("throttle", 0.0)) + 1.0) / 2.0
    brake = (float(state.get("brake", 0.0)) + 1.0) / 2.0
    channels = {
        "yaw": float(state.get("steering", 0.0)),
        "pitch": throttle - brake,
        "roll": float(state.get("dpad_x", 0)),
        "vertical": float(bool(state.get("paddle_right"))) - float(bool(state.get("paddle_left"))),
    }
    return {n: max(-limit, min(limit, expo(channels[n], p[n]) * limit)) for n in channels}
