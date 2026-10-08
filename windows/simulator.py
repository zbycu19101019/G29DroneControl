"""Small velocity-based flight model for checking G29 control feel."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


@dataclass
class FlightModel:
    x: float = 0.0  # metres east
    y: float = 0.0  # metres north
    z: float = 0.0  # metres above start
    heading: float = 0.0  # radians; 0 is north
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    room_half_size: float = 12.0
    boundary_stop: bool = False
    trail: deque[tuple[float, float]] = field(default_factory=lambda: deque([(0.0, 0.0)], maxlen=600))

    def reset(self) -> None:
        self.x = self.y = self.z = self.heading = 0.0
        self.vx = self.vy = self.vz = 0.0
        self.pitch_deg = self.roll_deg = 0.0
        self.boundary_stop = False
        self.trail.clear()
        self.trail.append((0.0, 0.0))

    def step(self, command: dict[str, float], dt: float) -> None:
        if not math.isfinite(dt) or any(not math.isfinite(float(command.get(k, 0))) for k in ("yaw", "pitch", "roll", "vertical")):
            raise ValueError("Nieprawidłowe dane symulacji")
        dt = max(0.0, min(0.1, dt))
        yaw = max(-1.0, min(1.0, float(command.get("yaw", 0.0))))
        pitch = max(-1.0, min(1.0, float(command.get("pitch", 0.0))))
        roll = max(-1.0, min(1.0, float(command.get("roll", 0.0))))
        vertical = max(-1.0, min(1.0, float(command.get("vertical", 0.0))))
        self.heading = (self.heading + yaw * math.radians(100) * dt) % (2 * math.pi)
        north = 4.0 * (pitch * math.cos(self.heading) - roll * math.sin(self.heading))
        east = 4.0 * (pitch * math.sin(self.heading) + roll * math.cos(self.heading))
        if self.z == 0.0 and vertical <= 0.0:
            north = east = 0.0
            self.vx = self.vy = 0.0
        alpha = 1.0 - math.exp(-dt / 0.45) if dt else 0.0
        self.vx += (east - self.vx) * alpha
        self.vy += (north - self.vy) * alpha
        self.vz += (vertical * 2.0 - self.vz) * alpha
        self.pitch_deg += (-pitch * 22.0 - self.pitch_deg) * alpha
        self.roll_deg += (roll * 28.0 - self.roll_deg) * alpha
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z = max(0.0, self.z + self.vz * dt)
        # Only a simulated room. No GPS fence or obstacle protection on a real aircraft.
        bound = self.room_half_size - .75
        self.boundary_stop = abs(self.x) >= bound or abs(self.y) >= bound or self.z >= 5
        if abs(self.x) >= bound:
            self.x = math.copysign(bound, self.x); self.vx = 0.0
        if abs(self.y) >= bound:
            self.y = math.copysign(bound, self.y); self.vy = 0.0
        if self.z >= 5:
            self.z = 5; self.vz = min(0, self.vz)
        if self.z == 0.0 and self.vz < 0:
            self.vz = 0.0
            self.vx = self.vy = 0.0
        if math.hypot(self.x - self.trail[-1][0], self.y - self.trail[-1][1]) > 0.05:
            self.trail.append((self.x, self.y))
