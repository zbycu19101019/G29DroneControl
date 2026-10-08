"""Conservative input shaping and truthful advisory status. NOT collision avoidance."""
import math

CHANNELS = ("yaw", "pitch", "roll", "vertical")


class InputLimiter:
    def __init__(self):
        self.last = dict.fromkeys(CHANNELS, 0.0)

    def reset(self):
        self.last = dict.fromkeys(CHANNELS, 0.0)

    def apply(self, command, dt, limit=.35):
        if not math.isfinite(dt) or dt < 0 or dt > .3:
            self.reset()
            return dict(self.last)
        delta = min(dt, .1) * 1.2
        for name in CHANNELS:
            value = command.get(name, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                self.reset()
                raise RuntimeError("Nieprawidłowy kanał — neutral")
            target = max(-limit, min(limit, value))
            self.last[name] += max(-delta, min(delta, target - self.last[name]))
        return dict(self.last)


def safety_summary(view, stopped=False):
    alerts = []
    if stopped:
        alerts.append("STOP aktywny — kanały testowe zablokowane")
    if not view.get("linkLive"):
        alerts.append("Brak uwierzytelnionego ACK telefonu")
    if not view.get("telemetryFresh"):
        alerts.append("Brak świeżej telemetrii drona")
    battery = view.get("battery")
    percent = battery.get("percent") if isinstance(battery, dict) else None
    if isinstance(percent, (int, float)) and not isinstance(percent, bool) and math.isfinite(percent):
        if percent <= 20:
            alerts.insert(0, f"Niska bateria {percent:.0f}% — zakończ test")
        elif percent <= 30:
            alerts.append(f"Bateria {percent:.0f}% — przygotuj zakończenie testu")
    else:
        alerts.append("Stan baterii nieznany")
    alerts.append("Mini 2 SE: brak wykrywania ścian / ochrony antykolizyjnej")
    return {"flightAllowed": False, "collisionAvoidance": False,
            "criticalBattery": percent is not None and isinstance(percent, (int, float)) and not isinstance(percent, bool) and math.isfinite(percent) and percent <= 20,
            "alerts": alerts}
