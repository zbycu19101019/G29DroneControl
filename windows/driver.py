"""SDL2 input for Logitech G29. Call every SDL method from the UI thread."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pygame

AXES = ("steering", "throttle", "brake", "clutch")


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_config(path: Path, config: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def init_pygame() -> None:
    # Tk owns the visible window. SDL's helper stays hidden, so joystick
    # input must remain enabled while SDL is in the background.
    os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
    pygame.display.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    pygame.joystick.init()


def list_devices() -> list[tuple[int, str, int, int, int]]:
    pygame.event.pump()
    found = []
    for index in range(pygame.joystick.get_count()):
        device = pygame.joystick.Joystick(index)
        device.init()
        found.append((index, device.get_name(), device.get_numaxes(), device.get_numbuttons(), device.get_numhats()))
    return found


def open_g29(index: int | None = None) -> pygame.joystick.Joystick:
    devices = list_devices()
    if index is None:
        index = next((i for i, name, *_ in devices if "g29" in name.lower()), None)
    if index is None or index not in [entry[0] for entry in devices]:
        raise RuntimeError("Nie wykryto G29. Sprawdź USB, zasilanie i tryb PS4.")
    device = pygame.joystick.Joystick(index)
    device.init()
    return device


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def axis_value(raw: float, name: str, config: dict[str, Any]) -> float:
    if not math.isfinite(raw):
        raise RuntimeError("Nieprawidłowa wartość osi G29")
    calibration = config.get("calibration", {}).get(name, {})
    deadzone = clamp(float(config.get("deadzone", 0.05)), 0.0, 0.5)
    if name == "steering":
        center = float(calibration.get("center", 0.0))
        minimum = float(calibration.get("min", -1.0))
        maximum = float(calibration.get("max", 1.0))
        denominator = max(0.1, center - minimum if raw < center else maximum - center)
        value = clamp((raw - center) / denominator, -1.0, 1.0)
        if config.get("axisInverted", {}).get(name, False):
            value = -value
        if abs(value) <= deadzone:
            return 0.0
        return (1.0 if value > 0 else -1.0) * (abs(value) - deadzone) / (1.0 - deadzone)
    if not calibration:
        return 0.0
    rest = float(calibration.get("rest", config.get("pedalRestRaw", {}).get(name, 1.0)))
    pressed = float(calibration.get("pressed", config.get("pedalPressedRaw", {}).get(name, -1.0)))
    if abs(pressed - rest) < 0.1:
        return 0.0
    value = clamp((raw - rest) / (pressed - rest), 0.0, 1.0)
    # Calibrated endpoints already encode either pedal direction. Inverting
    # normalized pedal travel would turn a released pedal into full throttle.
    return 0.0 if value <= deadzone else (value - deadzone) / (1.0 - deadzone)


class G29Reader:
    def __init__(self, device: pygame.joystick.Joystick, config: dict[str, Any]):
        self.device = device
        self.config = config
        self.instance_id = device.get_instance_id()

    def read(self) -> dict[str, Any]:
        pygame.event.pump()
        events = pygame.event.get()
        if any(e.type == pygame.JOYDEVICEREMOVED and e.instance_id == self.instance_id for e in events):
            raise RuntimeError("G29 został odłączony")
        if not self.device.get_init():
            raise RuntimeError("G29 nie jest zainicjalizowany")
        raw = [float(self.device.get_axis(i)) for i in range(self.device.get_numaxes())]
        state: dict[str, Any] = {"raw_axes": [round(v, 5) for v in raw], "device": self.device.get_name()}
        for name in AXES:
            axis = int(self.config.get("axisMap", {}).get(name, -1))
            state[name] = round(axis_value(raw[axis], name, self.config), 4) if 0 <= axis < len(raw) else 0.0
        buttons = [bool(self.device.get_button(i)) for i in range(self.device.get_numbuttons())]
        state["buttons"] = buttons
        for name in ("paddle_left", "paddle_right"):
            index = int(self.config.get("buttonMap", {}).get(name, -1))
            state[name] = buttons[index] if 0 <= index < len(buttons) else False
        state["dpad_x"], state["dpad_y"] = self.device.get_hat(0) if self.device.get_numhats() else (0, 0)
        return state
