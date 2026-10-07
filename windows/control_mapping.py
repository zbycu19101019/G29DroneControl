"""G29 input to neutral-centred simulator/control channels."""
from __future__ import annotations

import math
from typing import Any

PROFILES = {"NORMAL": 0.65, "AGRESYWNY": 0.15, "SMOOTH": 0.8, "CINEMATIC": 0.9, "GTA STYLE": 0.45}


def _curve(value: float, expo: float) -> float:
    if not math.isfinite(value):
        raise RuntimeError("Nieprawidłowa wartość kanału wejściowego")
    value = max(-1.0, min(1.0, value))
    return math.copysign((1.0 - expo) * abs(value) + expo * abs(value) ** 3, value)


def map_state(state: dict[str, Any], config: dict[str, Any], profile: str = "NORMAL") -> dict[str, float]:
    expo = PROFILES.get(profile.upper(), PROFILES["NORMAL"])
    limit = max(0.0, min(1.0, float(config.get("outputLimit", 0.6))))
    channels = {
        "yaw": _curve(float(state.get("steering", 0.0)), expo) * float(config.get("steeringSensitivity", 0.6)),
        "pitch": _curve(float(state.get("throttle", 0.0)) - float(state.get("brake", 0.0)), expo) * float(config.get("pitchSensitivity", 0.7)),
        "roll": _curve(float(state.get("dpad_x", 0)), expo) * float(config.get("rollSensitivity", 0.5)),
        "vertical": _curve(float(bool(state.get("paddle_right"))) - float(bool(state.get("paddle_left"))), expo) * float(config.get("verticalSensitivity", 0.5)),
    }
    return {name: round(max(-limit, min(limit, value)), 4) for name, value in channels.items()}
