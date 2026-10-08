"""Validate stored user settings before they reach the control loop."""
import math


def validate_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("Konfiguracja musi być obiektem")
    limits = {"updateRate": (20, 50), "deadzone": (0, .25), "outputLimit": (0, 1),
              "steeringSensitivity": (0, 1), "pitchSensitivity": (0, 1),
              "rollSensitivity": (0, 1), "verticalSensitivity": (0, 1), "transportPort": (1024, 65535)}
    for key, (low, high) in limits.items():
        if isinstance(config[key], bool) or not isinstance(config[key], (int, float)):
            raise ValueError(f"{key}: wymagana liczba")
        number = float(config[key])
        if not math.isfinite(number):
            raise ValueError(f"{key}: wartość musi być skończona")
        config[key] = max(low, min(high, number))
        if key in ("updateRate", "transportPort"):
            config[key] = int(config[key])
    for key in ("axisMap", "buttonMap", "axisInverted", "calibration"):
        if not isinstance(config.get(key, {}), dict):
            raise ValueError(f"{key}: wymagany obiekt")
    used = []
    for name, index in config["axisMap"].items():
        if not isinstance(index, int) or isinstance(index, bool) or index < -1 or index > 31:
            raise ValueError(f"Nieprawidłowe przypisanie osi {name}")
        if index >= 0:
            used.append(index)
    if len(set(used)) != len(used):
        raise ValueError("Jedna oś nie może sterować dwoma kanałami")
    for name, index in config.get("buttonMap", {}).items():
        if type(index) is not int or not -1 <= index <= 127:
            raise ValueError(f"Nieprawidłowe przypisanie przycisku {name}")
    if any(type(v) is not bool for v in config.get("axisInverted", {}).values()):
        raise ValueError("Odwrócenie osi musi być wartością logiczną")
    for name, values in config.get("calibration", {}).items():
        if not isinstance(values, dict) or any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 1.1 for v in values.values()):
            raise ValueError("Nieprawidłowa kalibracja")
        if not values:
            continue
        if name == "steering":
            if set(values) != {"min", "center", "max"} or not values["min"] < values["center"] < values["max"]:
                raise ValueError("Nieprawidłowy środek lub zakres kierownicy")
            if min(values["center"] - values["min"], values["max"] - values["center"]) < .1:
                raise ValueError("Zakres kierownicy jest za mały")
        elif name in ("throttle", "brake", "clutch"):
            if set(values) != {"rest", "pressed"} or abs(values["pressed"] - values["rest"]) < .1:
                raise ValueError("Nieprawidłowy zakres pedału")
        else:
            raise ValueError("Nieznana oś kalibracji")
    return config
