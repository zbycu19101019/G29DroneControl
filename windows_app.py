from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import pygame

from g29 import G29Reader, calibrate, choose_g29, init_pygame, list_joysticks, load_config
from windows.mapping import map_state
from windows.transport import JsonLineServer

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
BG = "#070b0d"; PANEL = "#0d1518"; PANEL2 = "#101d20"; GRID = "#1a3539"
CYAN = "#00f0c0"; AMBER = "#ffb000"; RED = "#ff3b55"; MUTED = "#6b8987"; WHITE = "#d9fff5"


class G29App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root; self.root.title("G29 // DRONE OPERATOR COCKPIT"); self.root.geometry("1120x760"); self.root.minsize(900, 650); self.root.configure(bg=BG); self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.config = load_config(CONFIG); self.reader = None; self.joystick = None; self.transport = None; self.running = False; self.seq = 0; self.last_tx = 0.0; self.packets = 0; self.events: queue.Queue[str] = queue.Queue()
        self.profile = tk.StringVar(value="NORMAL"); self.deadzone = tk.DoubleVar(value=float(self.config.get("deadzone", 0.05))); self.sensitivity = tk.DoubleVar(value=float(self.config.get("steeringSensitivity", 0.6)))
        self.status = tk.StringVar(value="G29 OFFLINE"); self.link = tk.StringVar(value="LINK: STANDBY")
        self.input_values = {n: tk.StringVar(value="+0.000") for n in ("steering", "throttle", "brake", "clutch")}; self.output_values = {n: tk.StringVar(value="+0.000") for n in ("yaw", "pitch", "roll", "vertical")}; self.input_nums = {n: 0.0 for n in self.input_values}; self.output_nums = {n: 0.0 for n in self.output_values}
        self.build_ui(); init_pygame(); self.refresh_devices(); self.root.after(350, lambda: self.connect_g29(show_error=False)); self.root.after(40, self.tick)

    def panel(self, parent, title):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=GRID, highlightthickness=1); tk.Label(frame, text=f"  {title}  ", bg=PANEL, fg=CYAN, font=("Consolas", 10, "bold")).pack(anchor="nw", padx=10, pady=(8, 4)); return frame

    def build_ui(self):
        header = tk.Frame(self.root, bg=BG); header.pack(fill="x", padx=18, pady=(14, 8)); tk.Label(header, text="G29 // DRONE OPERATOR", bg=BG, fg=CYAN, font=("Consolas", 22, "bold")).pack(side="left"); tk.Label(header, text="  CYBERNETIC FLIGHT CONTROL TERMINAL", bg=BG, fg=MUTED, font=("Consolas", 10)).pack(side="left", pady=8)
        self.led = tk.Canvas(header, width=15, height=15, bg=BG, highlightthickness=0); self.led.pack(side="right", padx=8); self.led_id = self.led.create_oval(2, 2, 13, 13, fill=RED, outline=""); tk.Label(header, textvariable=self.status, bg=BG, fg=WHITE, font=("Consolas", 11, "bold")).pack(side="right"); tk.Frame(self.root, bg=CYAN, height=1).pack(fill="x", padx=18)
        toolbar = tk.Frame(self.root, bg=BG); toolbar.pack(fill="x", padx=18, pady=10)
        for text, command, color in (("CONNECT G29", self.connect_g29, CYAN), ("CALIBRATE", self.start_calibration, AMBER), ("START LINK", self.start_transport, CYAN), ("EMERGENCY STOP", self.stop_all, RED)):
            tk.Button(toolbar, text=text, command=command, bg=PANEL2, fg=color, activebackground=GRID, activeforeground=WHITE, relief="flat", bd=0, padx=12, pady=7, font=("Consolas", 9, "bold")).pack(side="left", padx=(0, 7))
        tk.Label(toolbar, textvariable=self.link, bg=BG, fg=MUTED, font=("Consolas", 9)).pack(side="right")
        main = tk.Frame(self.root, bg=BG); main.pack(fill="both", expand=True, padx=18, pady=(0, 14)); left = tk.Frame(main, bg=BG); left.pack(side="left", fill="both", expand=True, padx=(0, 8)); right = tk.Frame(main, bg=BG, width=310); right.pack(side="right", fill="y", padx=(8, 0)); right.pack_propagate(False)
        hud = self.panel(left, "FLIGHT HUD // ARTIFICIAL HORIZON"); hud.pack(fill="both", expand=True, pady=(0, 8)); self.horizon = tk.Canvas(hud, bg="#071113", highlightthickness=0, height=330); self.horizon.pack(fill="both", expand=True, padx=12, pady=8)
        telemetry = self.panel(left, "TELEMETRY // OUTPUT CHANNELS"); telemetry.pack(fill="x"); self.output_bars = {}
        for name, color in (("YAW", CYAN), ("PITCH", AMBER), ("ROLL", CYAN), ("VERT", AMBER)):
            row = tk.Frame(telemetry, bg=PANEL); row.pack(fill="x", padx=12, pady=3); tk.Label(row, text=name, width=7, anchor="w", bg=PANEL, fg=MUTED, font=("Consolas", 9, "bold")).pack(side="left"); canvas = tk.Canvas(row, height=14, bg="#071113", highlightthickness=1, highlightbackground=GRID); canvas.pack(side="left", fill="x", expand=True, padx=8); val = tk.Label(row, text="+0.000", width=8, bg=PANEL, fg=color, font=("Consolas", 9)); val.pack(side="right"); self.output_bars[name.lower()] = (canvas, val, color)
        inputs = self.panel(right, "G29 // INPUT AXES"); inputs.pack(fill="x", pady=(0, 8)); self.input_bars = {}
        for name, color in (("steering", CYAN), ("throttle", AMBER), ("brake", RED), ("clutch", MUTED)):
            row = tk.Frame(inputs, bg=PANEL); row.pack(fill="x", padx=10, pady=4); tk.Label(row, text=name.upper(), width=9, anchor="w", bg=PANEL, fg=MUTED, font=("Consolas", 8, "bold")).pack(side="left"); canvas = tk.Canvas(row, height=13, bg="#071113", highlightthickness=1, highlightbackground=GRID); canvas.pack(side="left", fill="x", expand=True); tk.Label(row, textvariable=self.input_values[name], width=7, bg=PANEL, fg=color, font=("Consolas", 8)).pack(side="right"); self.input_bars[name] = (canvas, color)
        tuning = self.panel(right, "LIVE TUNING // RESPONSE CURVE"); tuning.pack(fill="x", pady=(0, 8)); tk.Label(tuning, text="PROFILE", bg=PANEL, fg=MUTED, font=("Consolas", 8)).pack(anchor="w", padx=12, pady=(4, 0)); menu = tk.OptionMenu(tuning, self.profile, "NORMAL", "AGRESYWNY", "SMOOTH", "GTA STYLE"); menu.config(bg=PANEL2, fg=CYAN, activebackground=GRID, activeforeground=WHITE, relief="flat", highlightthickness=0, width=18, font=("Consolas", 9)); menu.pack(fill="x", padx=10, pady=4); self.slider(tuning, "DEADZONE", self.deadzone, 0.0, 0.30); self.slider(tuning, "STEERING SENSITIVITY", self.sensitivity, 0.1, 1.0)
        watch = self.panel(right, "WATCHDOG // HEARTBEAT"); watch.pack(fill="x"); self.watch_text = tk.Label(watch, text="PACKETS: 0/s\nFAILSAFE: ARMED\nTX AGE: -- ms", justify="left", anchor="w", bg=PANEL, fg=MUTED, font=("Consolas", 9)); self.watch_text.pack(fill="x", padx=12, pady=5)
        self.raw_text = tk.Label(watch, text="RAW AXES: waiting for G29", justify="left", anchor="w", bg=PANEL, fg=AMBER, font=("Consolas", 8)); self.raw_text.pack(fill="x", padx=12, pady=(0, 7)); self.log = tk.Text(right, height=5, bg="#050809", fg=MUTED, insertbackground=CYAN, relief="flat", font=("Consolas", 8), state="disabled"); self.log.pack(fill="both", expand=True, pady=(8, 0))

    def slider(self, parent, text, variable, low, high):
        tk.Label(parent, text=text, bg=PANEL, fg=MUTED, font=("Consolas", 8)).pack(anchor="w", padx=12, pady=(5, 0)); tk.Scale(parent, variable=variable, from_=low, to=high, resolution=0.01, orient="horizontal", bg=PANEL, fg=CYAN, troughcolor="#203338", highlightthickness=0, showvalue=True, font=("Consolas", 8), command=self.tuning_changed).pack(fill="x", padx=8)

    def tuning_changed(self, _=None):
        self.config["deadzone"] = float(self.deadzone.get()); self.config["steeringSensitivity"] = float(self.sensitivity.get())

    def log_line(self, text): self.events.put(f"[{time.strftime('%H:%M:%S')}] {text}")

    def refresh_devices(self):
        try:
            devices = list_joysticks(); names = [d.get_name() for d in devices]
            for d in devices: d.quit()
            self.log_line("DEVICES: " + (", ".join(names) if names else "NONE"))
        except Exception as exc: self.log_line(f"SDL ERROR: {exc}")

    def connect_g29(self, show_error=True):
        try:
            self.joystick = choose_g29(); self.reader = G29Reader(self.joystick, self.config); self.running = True; self.status.set(f"G29 ONLINE // {self.joystick.get_numaxes()} AXES"); self.led.itemconfigure(self.led_id, fill=CYAN); self.log_line(f"G29 LINK ESTABLISHED // axes={self.joystick.get_numaxes()} buttons={self.joystick.get_numbuttons()}")
        except Exception as exc:
            if show_error: messagebox.showerror("G29", str(exc))
            self.log_line(f"G29 WAITING: {exc}")

    def start_calibration(self):
        if not self.joystick: self.connect_g29()
        if not self.joystick: return
        threading.Thread(target=self.calibration_worker, daemon=True).start(); self.log_line("CALIBRATION: MOVE ALL AXES")

    def calibration_worker(self):
        try: calibrate(self.joystick, self.config, CONFIG, interactive=False); self.log_line("CALIBRATION COMPLETE")
        except Exception as exc: self.log_line(f"CALIBRATION ERROR: {exc}")

    def start_transport(self):
        if self.transport: return
        try:
            self.transport = JsonLineServer(port=int(self.config.get("transportPort", 8765))); self.transport.start(); self.link.set("LINK: LISTENING // adb reverse tcp:8765 tcp:8765"); self.log_line("ANDROID LINK ARMED")
        except OSError as exc: messagebox.showerror("Transport", str(exc))

    def draw_bar(self, canvas, value, color, centered=False):
        canvas.delete("all"); w = max(20, canvas.winfo_width()); h = max(10, canvas.winfo_height()); canvas.create_rectangle(0, 0, w, h, fill="#071113", outline="")
        if centered:
            center = w / 2; end = center + value * (w / 2 - 2); x1, x2 = min(center, end), max(center, end); canvas.create_line(center, 1, center, h - 1, fill=MUTED); canvas.create_rectangle(x1, 2, x2, h - 2, fill=color, outline="")
        else: canvas.create_rectangle(1, 2, 1 + max(0, min(1, value)) * (w - 2), h - 2, fill=color, outline="")

    def draw_horizon(self):
        c = self.horizon; c.delete("all"); w = max(300, c.winfo_width()); h = max(220, c.winfo_height()); cx, cy = w / 2, h / 2; pitch = self.output_nums["pitch"] * h * 0.22
        c.create_rectangle(0, 0, w, h, fill="#102b39", outline=""); c.create_rectangle(0, cy + pitch, w, h, fill="#452c28", outline="")
        for d in range(-60, 61, 15):
            y = cy - d * h / 120 + pitch; span = 35 if d % 30 else 60; c.create_line(cx - span, y, cx + span, y, fill="#8db4b0", width=1)
        c.create_line(cx - 70, cy, cx - 18, cy, fill=AMBER, width=3); c.create_line(cx + 18, cy, cx + 70, cy, fill=AMBER, width=3); c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, outline=AMBER, width=2); c.create_text(12, 12, anchor="nw", text=f"ROLL {self.output_nums['roll']:+.2f}   PITCH {self.output_nums['pitch']:+.2f}   YAW {self.output_nums['yaw']:+.2f}", fill=CYAN, font=("Consolas", 10, "bold")); c.create_text(w - 12, 12, anchor="ne", text="HUD // LIVE", fill=AMBER, font=("Consolas", 9, "bold"))

    def tick(self):
        while not self.events.empty():
            self.log.configure(state="normal"); self.log.insert("end", self.events.get_nowait() + "\n"); self.log.see("end"); self.log.configure(state="disabled")
        if not self.running and self.reader is None and int(time.monotonic() * 10) % 20 == 0:
            self.connect_g29(show_error=False)
        if self.running and self.reader:
            try:
                self.reader.config = self.config; state = self.reader.read(); output = map_state(state, self.config, self.profile.get()); self.input_nums.update({n: float(state[n]) for n in self.input_nums}); self.output_nums.update(output); self.raw_text.configure(text="RAW AXES: " + "  ".join(f"A{i}={v:+.3f}" for i, v in enumerate(state.get("raw_axes", []))))
                for n in self.input_values: self.input_values[n].set(f"{self.input_nums[n]:+.3f}")
                for n in self.output_values: self.output_values[n].set(f"{self.output_nums[n]:+.3f}")
                if self.transport:
                    self.transport.accept_once(); sent = self.transport.send({"timestampMs": int(time.time() * 1000), "seq": self.seq, "input": state, "output": output, "heartbeat": True}); self.seq += 1; self.packets += int(sent); self.last_tx = time.monotonic() if sent else self.last_tx
            except Exception as exc: self.log_line(f"INPUT FAULT: {exc}"); self.stop_all()
        for n, (canvas, color) in self.input_bars.items(): self.draw_bar(canvas, (self.input_nums[n] + 1) / 2, color, False)
        for n, (canvas, value, color) in self.output_bars.items(): value.configure(text=f"{self.output_nums[n]:+.3f}"); self.draw_bar(canvas, self.output_nums[n], color, True)
        self.draw_horizon(); age = int((time.monotonic()-self.last_tx)*1000) if self.last_tx else "--"; self.watch_text.configure(text=f"PACKETS: {self.packets}/s\nFAILSAFE: ARMED\nTX AGE: {age} ms"); self.root.after(40, self.tick)

    def stop_all(self):
        self.running = False
        if self.transport: self.transport.close(); self.transport = None
        if self.joystick: self.joystick.quit(); self.joystick = None
        self.reader = None; self.status.set("EMERGENCY STOP // NEUTRAL"); self.link.set("LINK: DISARMED"); self.led.itemconfigure(self.led_id, fill=RED)
        for n in self.output_nums: self.output_nums[n] = 0.0

    def close(self): self.stop_all(); pygame.quit(); self.root.destroy()


if __name__ == "__main__":
    from cockpit import main

    main()
