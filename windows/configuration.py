"""Validate stored user settings before they reach the control loop."""
import math


def validate_config(config: dict) -> dict:
    limits = {"updateRate": (20, 50), "deadzone": (0, .25), "outputLimit": (0, 1),
              "steeringSensitivity": (0, 1), "pitchSensitivity": (0, 1),
              "rollSensitivity": (0, 1), "verticalSensitivity": (0, 1), "transportPort": (1024, 65535)}
    for key, (low, high) in limits.items():
        number = float(config[key])
        if not math.isfinite(number):
            raise ValueError(f"{key}: wartość musi być skończona")
        config[key] = max(low, min(high, number))
        if key in ("updateRate", "transportPort"):
            config[key] = int(config[key])
    used = []
    for name, index in config["axisMap"].items():
        if not isinstance(index, int) or isinstance(index, bool) or index < -1 or index > 31:
            raise ValueError(f"Nieprawidłowe przypisanie osi {name}")
        if index >= 0:
            used.append(index)
    if len(set(used)) != len(used):
        raise ValueError("Jedna oś nie może sterować dwoma kanałami")
    for values in config.get("calibration", {}).values():
        if not isinstance(values, dict) or any(not isinstance(v, (float, int)) or not math.isfinite(v) or abs(v) > 1.1 for v in values.values()):
            raise ValueError("Nieprawidłowa kalibracja")
    return config
