from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys

import pygame

from g29 import G29Reader, calibrate, choose_g29, init_pygame, load_config, print_devices

sys.path.insert(0, str(Path(__file__).resolve().parent / "windows"))
from mapping import map_state
from transport import JsonLineServer


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def run_reader(config: dict, mode: str) -> None:
    joystick = choose_g29()
    print(
        f"Połączono z: {joystick.get_name()} | "
        f"axes={joystick.get_numaxes()} buttons={joystick.get_numbuttons()} hats={joystick.get_numhats()}"
    )
    print("Ctrl+C kończy program. Stan jest odświeżany z częstotliwością konfiguracji.")
    reader = G29Reader(joystick, config)
    period = 1.0 / max(1.0, float(config.get("updateRate", 40)))
    try:
        while True:
            started = time.monotonic()
            state = reader.read()
            if mode == "json":
                print(json.dumps(state, ensure_ascii=False), flush=True)
            else:
                print(
                    "steering={steering:+.3f} throttle={throttle:+.3f} brake={brake:+.3f} "
                    "clutch={clutch:+.3f} paddles=L{paddle_left}/R{paddle_right} "
                    "dpad=({dpad_x:+d},{dpad_y:+d}) buttons={buttons}".format(**state),
                    flush=True,
                )
            time.sleep(max(0.0, period - (time.monotonic() - started)))
    except KeyboardInterrupt:
        print("\nZakończono.")
    finally:
        joystick.quit()


def run_android(config: dict) -> None:
    joystick = choose_g29()
    reader = G29Reader(joystick, config)
    server = JsonLineServer(port=int(config.get("transportPort", 8765)))
    server.start()
    period = 1.0 / max(1.0, float(config.get("updateRate", 40)))
    seq = 0
    try:
        while True:
            server.accept_once()
            started = time.monotonic()
            state = reader.read()
            output = map_state(state, config, str(config.get("profile", "NORMAL")))
            packet = {"timestampMs": int(time.time() * 1000), "seq": seq, "input": state, "output": output, "heartbeat": True}
            server.send(packet)
            seq += 1
            time.sleep(max(0.0, period - (time.monotonic() - started)))
    except KeyboardInterrupt:
        print("\nTransport zakończony; stan neutralny po stronie Androida.")
    finally:
        server.close(); joystick.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Etap 1: odczyt Logitech G29")
    parser.add_argument("--list-devices", action="store_true", help="wyświetl urządzenia joystick")
    parser.add_argument("--calibrate", action="store_true", help="zbierz min/max osi i zapisz do config.json")
    parser.add_argument("--debug", action="store_true", help="wypisuj stan w czytelnym formacie")
    parser.add_argument("--json", action="store_true", help="wypisuj stan jako JSON")
    parser.add_argument("--simulate", action="store_true", help="alias diagnostyczny; symulator drona będzie w etapie 9")
    parser.add_argument("--android", action="store_true", help="zarezerwowane dla etapu 2")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_pygame()
    try:
        if args.list_devices:
            print_devices()
            return
        config = load_config(CONFIG_PATH)
        joystick = choose_g29()
        if args.calibrate:
            calibrate(joystick, config, CONFIG_PATH)
            joystick.quit()
            return
        if args.android:
            joystick.quit()
            run_android(config)
            return
        run_reader(config, "json" if args.json else "text")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
