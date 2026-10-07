"""Guarded MAVLink adapter for an owned/autoriszed test vehicle.

Default mode is dry-run. Live mode is deliberately explicit and requires
heartbeat validation plus an interactive confirmation.
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

try:
    from pymavlink import mavutil
except ImportError:
    mavutil = None


@dataclass
class Channels:
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    vertical: float = 0.0

    def neutral(self) -> None:
        self.yaw = self.pitch = self.roll = self.vertical = 0.0


class MavlinkController:
    def __init__(self, endpoint: str, live: bool, timeout: float = 0.4):
        self.endpoint, self.live, self.timeout = endpoint, live, timeout
        self.link = None
        self.last_packet = time.monotonic()
        self.channels = Channels()

    def connect(self) -> None:
        if not self.live:
            print("MAVLink DRY-RUN: no packets will be sent")
            return
        if mavutil is None:
            raise RuntimeError("Install requirements.txt first")
        self.link = mavutil.mavlink_connection(self.endpoint)
        message = self.link.wait_heartbeat(timeout=5)
        if message is None:
            raise RuntimeError("No MAVLink heartbeat")
        print(f"Heartbeat: system={self.link.target_system} component={self.link.target_component}")
        if input("Type ENABLE LIVE to enable output: ").strip() != "ENABLE LIVE":
            raise RuntimeError("Live output not enabled")

    def set_channels(self, channels: Channels) -> None:
        self.channels = channels
        if time.monotonic() - self.last_packet > self.timeout:
            self.channels.neutral()
        if not self.live:
            print(f"DRY-RUN {self.channels}")
            return
        # This adapter intentionally does not arm or take off. The caller must
        # use the vehicle's documented manual/safety procedure.
        values = [1500 + int(max(-1.0, min(1.0, x)) * 400) for x in (channels.roll, channels.pitch, channels.throttle if hasattr(channels, 'throttle') else channels.vertical, channels.yaw)]
        self.link.mav.rc_channels_override_send(self.link.target_system, self.link.target_component, *values, *([65535] * 14))
        self.last_packet = time.monotonic()

    def emergency_stop(self) -> None:
        self.channels.neutral()
        if self.live and self.link:
            values = [1500, 1500, 1500, 1500] + [65535] * 14
            self.link.mav.rc_channels_override_send(self.link.target_system, self.link.target_component, *values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="udp:127.0.0.1:14550")
    parser.add_argument("--live", action="store_true", help="explicitly enable MAVLink output")
    args = parser.parse_args()
    controller = MavlinkController(args.endpoint, args.live)
    try:
        controller.connect()
        print("Controller ready. This sample sends neutral values only; integrate mapping with the Windows app.")
        while True:
            controller.set_channels(Channels())
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        controller.emergency_stop()


if __name__ == "__main__":
    main()
