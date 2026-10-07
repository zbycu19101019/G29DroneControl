"""Logitech G29 reader based on pygame/SDL2."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pygame


AXES = ("steering", "throttle", "brake", "clutch")


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_config(path: Path, config: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")


def init_pygame() -> None:
    os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
    pygame.init()
    pygame.joystick.init()


def list_joysticks() -> list[pygame.joystick.Joystick]:
    return [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]


def choose_g29() -> pygame.joystick.Joystick:
    devices = list_joysticks()
    if not devices:
        raise RuntimeError("Nie wykryto kontrolera. Sprawdź USB, zasilanie i przełącznik PS3/PS4 na G29.")

    preferred = next((d for d in devices if "g29" in d.get_name().lower()), devices[0])
    preferred.init()
    return preferred


def print_devices() -> None:
    devices = list_joysticks()
    if not devices:
        print("Brak urządzeń joystick/gamepad.")
        return
    for index, joystick in enumerate(devices):
        joystick.init()
        print(
            f"[{index}] {joystick.get_name()} | axes={joystick.get_numaxes()} "
            f"buttons={joystick.get_numbuttons()} hats={joystick.get_numhats()}"
        )
        for axis in range(joystick.get_numaxes()):
            print(f"    axis {axis}: {joystick.get_axis(axis): .3f}")
        joystick.quit()


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _deadzone(value: float, deadzone: float) -> float:
    magnitude = abs(value)
    if magnitude <= deadzone:
        return 0.0
    return (1.0 if value >= 0 else -1.0) * (magnitude - deadzone) / (1.0 - deadzone)


def _normalize_axis(raw: float, name: str, config: dict[str, Any]) -> float:
    calibration = config.get("calibration", {}).get(name, {})
    minimum = float(calibration.get("min", -1.0))
    maximum = float(calibration.get("max", 1.0))
    if maximum <= minimum:
        minimum, maximum = -1.0, 1.0
    value = 2.0 * (raw - minimum) / (maximum - minimum) - 1.0
    if config.get("axisInverted", {}).get(name, False):
        value = -value
    value = _clamp(value)
    value = _deadzone(value, float(config.get("deadzone", 0.05)))
    sensitivity = float(config.get("axisSensitivity", {}).get(name, 1.0))
    return _clamp(value * sensitivity)


class G29Reader:
    def __init__(self, joystick: pygame.joystick.Joystick, config: dict[str, Any]):
        self.joystick = joystick
        self.config = config

    def read(self) -> dict[str, Any]:
        pygame.event.pump()
        # Drain SDL events so Windows keeps delivering fresh wheel reports
        # while the Tk event loop is running.
        pygame.event.get()
        axis_map = self.config.get("axisMap", {})
        state: dict[str, Any] = {}
        state["raw_axes"] = [round(float(self.joystick.get_axis(i)), 5) for i in range(self.joystick.get_numaxes())]
        state["device"] = self.joystick.get_name()
        for name in AXES:
            axis = int(axis_map.get(name, -1))
            raw = self.joystick.get_axis(axis) if 0 <= axis < self.joystick.get_numaxes() else 0.0
            state[name] = round(_normalize_axis(float(raw), name, self.config), 4)

        buttons = [bool(self.joystick.get_button(i)) for i in range(self.joystick.get_numbuttons())]
        button_map = self.config.get("buttonMap", {})
        state["paddle_left"] = bool(buttons[int(button_map.get("paddle_left", -1))]) if 0 <= int(button_map.get("paddle_left", -1)) < len(buttons) else False
        state["paddle_right"] = bool(buttons[int(button_map.get("paddle_right", -1))]) if 0 <= int(button_map.get("paddle_right", -1)) < len(buttons) else False
        state["buttons"] = buttons
        state["dpad_x"], state["dpad_y"] = (self.joystick.get_hat(0) if self.joystick.get_numhats() else (0, 0))
        return state


def calibrate(joystick: pygame.joystick.Joystick, config: dict[str, Any], path: Path, interactive: bool = True) -> None:
    print(f"Kalibracja: {joystick.get_name()}")
    print("Poruszaj kierownicą i każdym pedałem przez cały zakres.")
    if interactive:
        input("Naciśnij Enter, aby rozpocząć...")
    else:
        print("Kalibracja rozpocznie się za 2 sekundy...")
        time.sleep(2)
    started = time.monotonic()
    samples: dict[str, list[float]] = {name: [] for name in AXES}
    print("Zbieram próbki przez 8 sekund... naciśnij Enter wcześniej, aby zakończyć.")
    while time.monotonic() - started < 8.0:
        pygame.event.pump()
        for name in AXES:
            axis = int(config.get("axisMap", {}).get(name, -1))
            if 0 <= axis < joystick.get_numaxes():
                samples[name].append(float(joystick.get_axis(axis)))
        time.sleep(0.01)
        # The loop deliberately does not use input() here: it would block SDL events.
    calibration = config.setdefault("calibration", {})
    for name, values in samples.items():
        if values:
            calibration[name] = {"min": round(min(values), 5), "max": round(max(values), 5)}
    save_config(path, config)
    print(f"Zapisano kalibrację w {path}.")
