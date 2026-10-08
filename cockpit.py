"""G29 cockpit. Displays real SDL input and simulated control commands."""
from __future__ import annotations

import math
import json
import statistics
import sys
import time
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import messagebox, ttk

import pygame

from windows.control_mapping import PROFILES, map_state
from windows.driver import AXES, G29Reader, init_pygame, list_devices, load_config, open_g29, save_config
from windows.bridge_link import JsonLineServer
from windows.configuration import validate_config
from windows.connection_panel import ConnectionPanel
from windows.dji_telemetry import DjiTelemetryPanel
from windows.dji_telemetry import diagnostics_view
from windows.safety import InputLimiter, safety_summary
from windows.simulator import FlightModel
from windows.video_link import ScreenViewer

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
BUNDLED_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
CONFIG_PATH = APP_DIR / "config.json"
BG = "#f2f5f9"
PANEL = "#ffffff"
EDGE = "#d7e0e9"
NEON = "#2563eb"
AMBER = "#a16207"
RED = "#b91c1c"
WHITE = "#142335"
MUTED = "#64748b"


def default_config() -> dict:
    return {
        "updateRate": 40,
        "deadzone": 0.05,
        "steeringSensitivity": 0.6,
        "pitchSensitivity": 0.7,
        "rollSensitivity": 0.5,
        "verticalSensitivity": 0.5,
        "outputLimit": 0.6,
        "transportPort": 8765,
        "profile": "NORMAL",
        "axisMap": {"steering": 0, "throttle": 1, "brake": 2, "clutch": 3},
        "axisInverted": {name: False for name in AXES},
        "pedalRestRaw": {name: 1.0 for name in AXES if name != "steering"},
        "pedalPressedRaw": {name: -1.0 for name in AXES if name != "steering"},
        "buttonMap": {"paddle_left": 4, "paddle_right": 5},
    }


def merged_config() -> dict:
    config = default_config()
    source = CONFIG_PATH if CONFIG_PATH.exists() else BUNDLED_DIR / "config.json"
    if source.exists():
        loaded = load_config(source)
        if not isinstance(loaded, dict):
            raise ValueError("Konfiguracja musi być obiektem JSON")
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key].update(value)
            else:
                config[key] = value
    return validate_config(config)


class Cockpit:
    def __init__(self, root: tk.Tk):
        self.root = root
        try:
            self.config = merged_config()
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            messagebox.showwarning("Konfiguracja", f"Nieprawidłowe ustawienia: {exc}\nUżywam bezpiecznych domyślnych. Plik nie został zmieniony.")
            self.config = default_config()
        self.root.title("G29 Operator V5 • diagnostyka i symulator")
        self.root.geometry("1180x820")
        self.root.minsize(960, 700)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda _event: self.stop())
        self.root.report_callback_exception = self.callback_error
        self.reader: G29Reader | None = None
        self.device = None
        self.link: JsonLineServer | None = None
        self.connection_panel = None
        self.dji_panel = None
        self.video = ScreenViewer(APP_DIR)
        self.video_status = tk.StringVar(value="WIDEO: TELEFON / PILOT → OBRAZ DJI FLY (osobne okno, tylko podgląd)")
        self.seq = 0
        self.sent_window = 0
        self.sent_rate = 0
        self.rate_start = time.monotonic()
        self.last_tx = 0.0
        self.last_read = 0.0
        self.next_retry = time.monotonic() + 0.6
        self.stop_latched = False
        self.calibration: dict | None = None
        self.demo_started: float | None = None
        self.raw_samples: deque[list[float]] = deque(maxlen=24)
        self.state: dict = {}
        self.output = {name: 0.0 for name in ("yaw", "pitch", "roll", "vertical")}
        self.limiter = InputLimiter()
        self.inputs_enabled = tk.BooleanVar(value=False)
        self.cautious = tk.BooleanVar(value=True)
        self.safety_status = tk.StringVar(value="Sterowanie lotem wyłączone • Mini 2 SE nie wykrywa ścian")
        self.flight = FlightModel()
        self.last_sim_step = time.monotonic()
        self.device_choices: list[tuple[int, str, int, int, int]] = []
        self.device_choice = tk.StringVar(value="AUTO: LOGITECH G29")
        self.profile = tk.StringVar(value=str(self.config.get("profile", "NORMAL")))
        self.deadzone = tk.DoubleVar(value=float(self.config["deadzone"]))
        self.sensitivity = tk.DoubleVar(value=float(self.config["steeringSensitivity"]))
        self.limit = tk.DoubleVar(value=float(self.config["outputLimit"]))
        self.status = tk.StringVar(value="G29: WYSZUKIWANIE")
        self.link_status = tk.StringVar(value="ANDROID: LINK WYŁĄCZONY")
        self.raw_status = tk.StringVar(value="RAW: --")
        self.help_status = tk.StringVar(value="Porusz kierownicą. Oś, która się zmienia, przypisz jako STEERING. Pedały wymagają kalibracji.")
        self.mapping_vars = {name: tk.StringVar(value=str(self.config["axisMap"].get(name, -1))) for name in AXES}
        self.input_labels: dict[str, tk.StringVar] = {name: tk.StringVar(value="0.000") for name in AXES}
        self.output_labels: dict[str, tk.StringVar] = {name: tk.StringVar(value="+0.000") for name in self.output}
        self.build_ui()
        init_pygame()
        self.refresh_devices()
        self.last_sim_step = time.monotonic()
        self.tick_job = self.root.after(25, self.tick)

    def section(self, parent, title: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=EDGE, highlightthickness=1)
        tk.Label(frame, text=title, bg=PANEL, fg=NEON, font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 5))
        return frame

    def button(self, parent, text, command, accent=NEON):
        return tk.Button(parent, text=text, command=command, bg="#eaf0f8", fg=accent, activebackground=EDGE, activeforeground=WHITE, font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=8, cursor="hand2")

    def build_ui(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=18, pady=(15, 8))
        tk.Label(top, text="G29 Operator", bg=BG, fg=WHITE, font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Label(top, text="V5 • Windows + Android", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left", padx=16)
        self.led = tk.Canvas(top, width=20, height=20, bg=BG, highlightthickness=0)
        self.led.pack(side="right", padx=10)
        self.led_circle = self.led.create_oval(3, 3, 17, 17, fill=RED, outline="")
        tk.Label(top, textvariable=self.status, bg=BG, fg=WHITE, font=("Segoe UI", 11)).pack(side="right")
        tk.Frame(self.root, bg=NEON, height=1).pack(fill="x", padx=18)

        toolbar = tk.Frame(self.root, bg=BG)
        toolbar.pack(fill="x", padx=18, pady=10)
        self.button(toolbar, "ODŚWIEŻ USB", self.refresh_devices).pack(side="left", padx=(0, 8))
        self.button(toolbar, "POŁĄCZ G29", self.connect_selected).pack(side="left", padx=(0, 8))
        self.button(toolbar, "KALIBRACJA", self.start_calibration, AMBER).pack(side="left", padx=(0, 8))
        self.button(toolbar, "TELEFON / PILOT", self.open_connection_panel).pack(side="left", padx=(0, 8))
        self.button(toolbar, "DEMO LOT", self.start_demo, AMBER).pack(side="left", padx=(0, 8))
        self.button(toolbar, "STOP", self.stop, RED).pack(side="left", padx=(0, 8))
        self.button(toolbar, "ZAPISZ", self.save_settings, AMBER).pack(side="right")
        tk.Label(self.root, textvariable=self.safety_status, bg="#fff7ed", fg="#9a3412", anchor="w",
                 justify="left", wraplength=1100, font=("Segoe UI", 10), padx=12, pady=9).pack(fill="x", padx=18, pady=(0, 10))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, minsize=390)
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        sidebar = tk.Frame(body, bg=BG, width=390)
        sidebar.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        sidebar.pack_propagate(False)
        self.side_canvas = tk.Canvas(sidebar, bg=BG, highlightthickness=0, width=370)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=self.side_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.side_canvas.pack(side="left", fill="both", expand=True)
        self.side_canvas.configure(yscrollcommand=scrollbar.set)
        right = tk.Frame(self.side_canvas, bg=BG)
        side_window = self.side_canvas.create_window(0, 0, window=right, anchor="nw")
        right.bind("<Configure>", lambda _event: self.side_canvas.configure(scrollregion=self.side_canvas.bbox("all")))
        self.side_canvas.bind("<Configure>", lambda event: self.side_canvas.itemconfigure(side_window, width=event.width))
        self.root.bind("<MouseWheel>", self.scroll_sidebar, add="+")

        horizon_panel = self.section(left, "WIZUALIZACJA POLECEŃ / HORYZONT")
        horizon_panel.pack(fill="both", expand=True, pady=(0, 8))
        flight_view = tk.Frame(horizon_panel, bg=PANEL)
        flight_view.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.horizon = tk.Canvas(flight_view, bg="#6d9fbe", highlightthickness=0)
        self.horizon.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.map_canvas = tk.Canvas(flight_view, bg="#f8fafc", highlightthickness=0)
        self.map_canvas.pack(side="right", fill="both", expand=True, padx=(5, 0))
        self.flight_data = tk.Label(horizon_panel, text="DRON SYMULOWANY  X +0.0 m  Y +0.0 m  H 0.0 m  V 0.0 m/s", bg=PANEL, fg=WHITE, font=("Segoe UI", 9), anchor="w")
        self.flight_data.pack(fill="x", padx=12, pady=(0, 10))
        self.button(horizon_panel, "RESET SYMULACJI", self.reset_simulator, AMBER).pack(anchor="w", padx=12, pady=(0, 10))
        channel_panel = self.section(left, "WYJŚCIE / KOMENDY SYMULATORA")
        channel_panel.pack(fill="x")
        self.channel_bars = {}
        for name in self.output:
            row = tk.Frame(channel_panel, bg=PANEL)
            row.pack(fill="x", padx=12, pady=5)
            tk.Label(row, text=name.upper(), bg=PANEL, fg=MUTED, font=("Segoe UI", 10), width=9, anchor="w").pack(side="left")
            bar = tk.Canvas(row, height=16, bg=BG, highlightbackground=EDGE, highlightthickness=1)
            bar.pack(side="left", fill="x", expand=True, padx=8)
            tk.Label(row, textvariable=self.output_labels[name], bg=PANEL, fg=NEON, font=("Segoe UI", 10), width=8).pack(side="right")
            self.channel_bars[name] = bar
        tk.Frame(channel_panel, bg=PANEL, height=8).pack()
        tk.Label(left, textvariable=self.video_status, bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=620, justify="left", anchor="w").pack(fill="x", pady=6)

        input_panel = self.section(right, "G29 / SUROWE I PRZELICZONE OSIE")
        input_panel.pack(fill="x", pady=(0, 8))
        self.raw_line = tk.Label(input_panel, textvariable=self.raw_status, bg=PANEL, fg=AMBER, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=350)
        self.raw_line.pack(fill="x", padx=12, pady=4)
        self.input_bars = {}
        for name in AXES:
            row = tk.Frame(input_panel, bg=PANEL)
            row.pack(fill="x", padx=12, pady=4)
            tk.Label(row, text=name.upper(), bg=PANEL, fg=MUTED, font=("Segoe UI", 9), width=10, anchor="w").pack(side="left")
            bar = tk.Canvas(row, height=13, bg=BG, highlightbackground=EDGE, highlightthickness=1)
            bar.pack(side="left", fill="x", expand=True, padx=5)
            tk.Label(row, textvariable=self.input_labels[name], bg=PANEL, fg=WHITE, font=("Segoe UI", 9), width=7).pack(side="right")
            self.input_bars[name] = bar
        tk.Label(input_panel, textvariable=self.help_status, bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=350, justify="left").pack(fill="x", padx=12, pady=(5, 10))

        mapping = self.section(right, "URZĄDZENIE / PRZYPISANIE OSI")
        mapping.pack(fill="x", pady=(0, 8))
        self.device_menu = ttk.Combobox(mapping, textvariable=self.device_choice, state="readonly")
        self.device_menu.pack(fill="x", padx=12, pady=3)
        grid = tk.Frame(mapping, bg=PANEL)
        grid.pack(fill="x", padx=12, pady=(4, 10))
        for row, name in enumerate(AXES):
            tk.Label(grid, text=name.upper(), bg=PANEL, fg=MUTED, font=("Segoe UI", 9), width=12, anchor="w").grid(row=row, column=0, sticky="w", pady=2)
            field = ttk.Combobox(grid, textvariable=self.mapping_vars[name], width=7, state="readonly")
            field.grid(row=row, column=1, sticky="w", padx=4)
            field.bind("<<ComboboxSelected>>", lambda _event, axis=name: self.update_axis_map(axis))
            setattr(self, f"map_{name}", field)

        tuning = self.section(right, "CZUŁOŚĆ / PROFILE")
        tuning.pack(fill="x", pady=(0, 8))
        menu = ttk.Combobox(tuning, textvariable=self.profile, values=list(PROFILES), state="readonly")
        menu.pack(fill="x", padx=12, pady=4)
        self.add_slider(tuning, "MARTWA STREFA", self.deadzone, 0, 0.25)
        self.add_slider(tuning, "CZUŁOŚĆ KIEROWNICY", self.sensitivity, 0.1, 1.0)
        self.add_slider(tuning, "LIMIT WYJŚCIA", self.limit, 0.1, 1.0)

        watch = self.section(right, "ŁĄCZE / WATCHDOG")
        watch.pack(fill="x", pady=(0, 8), before=mapping)
        safe = self.section(right, "Zabezpieczenia kanałów testowych")
        safe.pack(fill="x", pady=(0, 8), before=mapping)
        tk.Checkbutton(safe, text="Włącz kanały G29 do mostka (nie do drona)", variable=self.inputs_enabled,
                       command=self.confirm_test_inputs, bg=PANEL, fg=WHITE, selectcolor=PANEL,
                       activebackground=PANEL, wraplength=330).pack(anchor="w", padx=12, pady=6)
        tk.Checkbutton(safe, text="Tryb ostrożny: limit 35% + łagodne narastanie", variable=self.cautious,
                       bg=PANEL, fg=WHITE, selectcolor=PANEL, activebackground=PANEL, wraplength=330).pack(anchor="w", padx=12, pady=(0, 8))
        tk.Label(watch, textvariable=self.link_status, bg=PANEL, fg=AMBER, font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=12, pady=(2, 0))
        self.metrics = tk.Label(watch, text="TX: 0/s | OSTATNIA: -- | BRAK POTWIERDZENIA Z ANDROIDA", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w", wraplength=350, justify="left")
        self.metrics.pack(fill="x", padx=12, pady=(0, 10))
        self.log_box = tk.Text(right, bg="#f8fafc", fg=MUTED, font=("Segoe UI", 8), height=5, relief="flat", state="disabled")
        self.log_box.pack(fill="both", expand=True)

    def scroll_sidebar(self, event):
        canvas = self.side_canvas
        if canvas.winfo_rootx() <= event.x_root <= canvas.winfo_rootx() + canvas.winfo_width() and canvas.winfo_rooty() <= event.y_root <= canvas.winfo_rooty() + canvas.winfo_height():
            canvas.yview_scroll(-int(event.delta / 120), "units")

    def add_slider(self, parent, label, variable, low, high):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w", width=19).pack(side="left")
        tk.Label(row, textvariable=variable, bg=PANEL, fg=NEON, font=("Segoe UI", 8), width=4).pack(side="right")
        tk.Scale(row, variable=variable, from_=low, to=high, resolution=0.01, orient="horizontal", showvalue=False, bg=PANEL, fg=NEON, troughcolor=EDGE, highlightthickness=0, command=self.live_tuning).pack(fill="x", expand=True, side="left")

    def log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        if int(self.log_box.index("end-1c").split(".")[0]) > 300:
            self.log_box.delete("1.0", "51.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def refresh_devices(self):
        self.device_choices = list_devices()
        values = ["AUTO: LOGITECH G29"] + [f"{index}: {name} ({axes} osi, {buttons} przycisków)" for index, name, axes, buttons, _ in self.device_choices]
        self.device_menu.configure(values=values)
        if self.device_choice.get() not in values:
            self.device_choice.set(values[0])
        axis_count = max([entry[2] for entry in self.device_choices], default=4)
        for name in AXES:
            getattr(self, f"map_{name}").configure(values=["-1"] + [str(i) for i in range(axis_count)])
        self.log("WYKRYTO: " + (", ".join(entry[1] for entry in self.device_choices) if self.device_choices else "brak urządzeń"))

    def connect_selected(self, quiet=False):
        if self.reader is not None:
            if quiet:
                return
            self.stop()
        try:
            choice = self.device_choice.get()
            selected = None if choice.startswith("AUTO") else int(choice.split(":", 1)[0])
            self.device = open_g29(selected)
            guid = self.device.get_guid()
            if self.config.get("calibration") and self.config.get("calibrationDeviceGuid") != guid:
                self.config["calibration"] = {}
                self.log("Kalibracja nie jest przypisana do tej kierownicy; pedały zablokowane do ponownej kalibracji.")
            self.reader = G29Reader(self.device, self.config)
            self.stop_latched = False
            self.status.set(f"G29 ONLINE / {self.device.get_numaxes()} OSIE")
            self.log(f"POŁĄCZONO: {self.device.get_name()}")
        except (pygame.error, RuntimeError, ValueError) as exc:
            self.reader = None
            if not quiet:
                messagebox.showerror("G29", str(exc))

    def update_axis_map(self, name):
        value = int(self.mapping_vars[name].get())
        if self.config["axisMap"].get(name) == value:
            return
        if value >= 0 and any(key != name and axis == value for key, axis in self.config["axisMap"].items()):
            self.mapping_vars[name].set(str(self.config["axisMap"][name]))
            messagebox.showwarning("Przypisanie osi", "Ta oś jest już przypisana. Najpierw ustaw poprzedni kanał na -1 (wyłączony).")
            return
        self.neutral()
        if self.link:
            self.link.close()
            self.link = None
        self.calibration = None
        self.config["axisMap"][name] = value
        self.config.get("calibration", {}).pop(name, None)
        self.log(f"OŚ {name.upper()} -> A{value}; wymagana ponowna kalibracja")

    def live_tuning(self, _=None):
        self.config["deadzone"] = float(self.deadzone.get())
        self.config["steeringSensitivity"] = float(self.sensitivity.get())
        self.config["outputLimit"] = float(self.limit.get())

    def confirm_test_inputs(self):
        if self.inputs_enabled.get() and not messagebox.askokcancel("Kanały testowe", "Dron nie jest sterowany przez ten mostek. Potwierdź test na ziemi, bez śmigieł.\nMini 2 SE nie ma ochrony przed ścianami.", parent=self.root):
            self.inputs_enabled.set(False)
        self.limiter.reset()

    def callback_error(self, error_type, error, traceback):
        self.stop()
        self.log("Błąd aplikacji: " + error_type.__name__ + ". Wyjścia zablokowane.")
        self.safety_status.set("Błąd aplikacji — STOP. Kanały testowe wyzerowane; dron nie jest sterowany.")

    def save_settings(self):
        self.live_tuning()
        self.config["profile"] = self.profile.get()
        try:
            save_config(CONFIG_PATH, self.config)
            self.log("ZAPISANO USTAWIENIA")
        except OSError as exc:
            messagebox.showerror("Zapis konfiguracji", str(exc))

    def start_calibration(self):
        self.inputs_enabled.set(False)
        if self.reader is None:
            self.connect_selected()
        if self.reader is None:
            return
        if self.link:
            self.link.close()
            self.link = None
        self.demo_started = None
        self.calibration = {"phase": "rest", "until": time.monotonic() + 1.5, "rest": [], "range": {name: [] for name in AXES}}
        self.log("KALIBRACJA: trzymaj kierownicę prosto, puść pedały (1,5 s)")
        self.help_status.set("Kalibracja: trzymaj kierownicę prosto i nie naciskaj pedałów.")

    def calibration_step(self, state):
        cal = self.calibration
        if cal is None:
            return
        raw = state["raw_axes"]
        now = time.monotonic()
        if cal["phase"] == "rest":
            cal["rest"].append(raw)
            if now >= cal["until"]:
                cal["phase"] = "range"
                cal["until"] = now + 10.0
                self.log("KALIBRACJA: obróć koło do obu krańców i wciśnij każdy pedał")
                self.help_status.set("Kalibracja: pełny obrót w lewo/prawo i każdy pedał do końca (10 s).")
        else:
            for name in AXES:
                index = int(self.config["axisMap"].get(name, -1))
                if 0 <= index < len(raw):
                    cal["range"][name].append(raw[index])
            if now >= cal["until"]:
                self.finish_calibration()

    def finish_calibration(self):
        cal = self.calibration
        self.calibration = None
        if cal is None or not cal["rest"]:
            return
        baseline = cal["rest"][-min(10, len(cal["rest"])):]
        saved = []
        for name in AXES:
            index = int(self.config["axisMap"].get(name, -1))
            values = cal["range"][name]
            if not values or index >= len(baseline[0]):
                continue
            rest = statistics.median(sample[index] for sample in baseline)
            low, high = min(values), max(values)
            if name == "steering" and low < rest - 0.15 and high > rest + 0.15:
                self.config.setdefault("calibration", {})[name] = {"center": rest, "min": low, "max": high}
                saved.append(name)
            elif name != "steering":
                pressed = low if abs(low - rest) > abs(high - rest) else high
                if abs(pressed - rest) >= 0.2:
                    self.config.setdefault("calibration", {})[name] = {"rest": rest, "pressed": pressed}
                    saved.append(name)
        if saved:
            self.config["calibrationDeviceGuid"] = self.device.get_guid()
            self.save_settings()
        self.help_status.set("Kalibracja: " + (", ".join(saved) if saved else "brak pełnego ruchu osi; sprawdź RAW"))
        self.log("KALIBRACJA ZAKOŃCZONA: " + (", ".join(saved) if saved else "bez nowych danych"))

    def open_connection_panel(self):
        if self.connection_panel and not self.connection_panel.closed:
            self.connection_panel.window.lift()
            return
        self.connection_panel = ConnectionPanel(self, APP_DIR / "G29Bridge.apk")

    def start_link(self):
        if self.calibration is not None:
            messagebox.showwarning("Kalibracja", "Poczekaj na zakończenie kalibracji.")
            return
        if self.demo_started is not None:
            messagebox.showwarning("Demo", "Poczekaj na zakończenie pokazu lotu.")
            return
        if self.link is not None:
            return
        try:
            self.link = JsonLineServer(port=int(self.config.get("transportPort", 8765)))
            self.link.start()
            self.log("Mostek telefonu nasłuchuje: localhost:" + str(self.config["transportPort"]) + " / diagnostyka, bez adaptera DJI")
        except OSError as exc:
            self.link = None
            messagebox.showerror("Port TCP", str(exc))

    def start_demo(self):
        self.inputs_enabled.set(False)
        if self.link is not None:
            self.link.close()
            self.link = None
        self.calibration = None
        self.flight.reset()
        self.demo_started = time.monotonic()
        self.help_status.set("DEMO: start, lot do przodu, obrót, lot po łuku i lądowanie. Wyjście Android wyłączone.")
        self.log("DEMO LOTU: wyłącznie symulator")

    @staticmethod
    def demo_command(elapsed: float) -> dict[str, float]:
        if elapsed < 2.0:
            return {"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "vertical": 0.55}
        if elapsed < 5.0:
            return {"yaw": 0.0, "pitch": 0.55, "roll": 0.0, "vertical": 0.0}
        if elapsed < 8.0:
            return {"yaw": 0.42, "pitch": 0.45, "roll": 0.12, "vertical": 0.0}
        if elapsed < 10.0:
            return {"yaw": 0.0, "pitch": 0.35, "roll": 0.0, "vertical": 0.0}
        if elapsed < 12.0:
            return {"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "vertical": -0.6}
        return {"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "vertical": 0.0}

    def neutral(self):
        self.limiter.reset()
        self.output = {name: 0.0 for name in self.output}
        if self.link is not None and self.link.connected:
            self.link.send({"timestampMs": int(time.time() * 1000), "seq": self.seq, "output": self.output,
                            "heartbeat": True, "inputConnected": False, "emergency": True})
            self.seq += 1

    def clear_inputs(self):
        self.state = {}
        self.raw_status.set("RAW: --")
        for name in AXES:
            self.input_labels[name].set("0.000")
            self.draw_bar(self.input_bars[name], 0.0, NEON, name == "steering")

    def reset_simulator(self):
        self.flight.reset()
        self.log("SYMULACJA: pozycja i trasa wyzerowane")

    def stop(self):
        self.inputs_enabled.set(False)
        self.stop_latched = True
        self.calibration = None
        self.demo_started = None
        self.neutral()
        if self.link is not None:
            self.link.close()
            self.link = None
        if self.device is not None:
            try:
                self.device.quit()
            except pygame.error:
                pass
            self.device = None
        self.reader = None
        self.clear_inputs()
        self.status.set("STOP / WYJŚCIA ZERO")
        self.link_status.set("ANDROID: LINK WYŁĄCZONY")
        self.help_status.set("STOP aktywny. Kliknij POŁĄCZ G29, aby wznowić odczyt.")
        self.log("STOP: zerowe polecenie, łącze zamknięte")

    def draw_bar(self, canvas, value, color=NEON, centered=False):
        canvas.delete("all")
        width = max(10, canvas.winfo_width())
        height = max(8, canvas.winfo_height())
        if centered:
            center = width / 2
            end = center + max(-1, min(1, value)) * center
            canvas.create_line(center, 0, center, height, fill=MUTED)
            canvas.create_rectangle(min(center, end), 2, max(center, end), height - 2, fill=color, outline="")
        else:
            canvas.create_rectangle(1, 2, 1 + max(0, min(1, value)) * (width - 2), height - 2, fill=color, outline="")

    def draw_horizon(self):
        canvas = self.horizon
        canvas.delete("all")
        width = max(100, canvas.winfo_width())
        height = max(100, canvas.winfo_height())
        center_x, center_y = width / 2, height / 2
        pitch = -self.flight.pitch_deg / 25.0 * height * 0.35
        roll_angle = math.radians(self.flight.roll_deg)
        slope = math.tan(roll_angle)
        left_y = center_y + pitch - slope * center_x
        right_y = center_y + pitch + slope * center_x
        canvas.create_rectangle(0, 0, width, height, fill="#6d9fbe", outline="")
        canvas.create_polygon(0, left_y, width, right_y, width, height, 0, height, fill="#b69c7b", outline="")
        canvas.create_line(0, left_y, width, right_y, fill="#ffffff", width=2)
        for offset in (-60, -30, 30, 60):
            y = center_y + pitch + offset
            canvas.create_line(center_x - 25, y - slope * 25, center_x + 25, y + slope * 25, fill=MUTED)
        canvas.create_line(center_x - 65, center_y, center_x - 14, center_y, fill=AMBER, width=3)
        canvas.create_line(center_x + 14, center_y, center_x + 65, center_y, fill=AMBER, width=3)
        canvas.create_oval(center_x - 5, center_y - 5, center_x + 5, center_y + 5, outline=AMBER, width=2)
        canvas.create_text(15, 18, anchor="nw", text="Orientacja symulatora", fill="#ffffff", font=("Segoe UI", 11, "bold"))
        canvas.create_text(width / 2, height - 18, text="SYMULACJA • nie telemetria drona", fill="#ffffff", font=("Segoe UI", 8))

    def draw_flight_map(self):
        canvas = self.map_canvas
        canvas.delete("all")
        width = max(100, canvas.winfo_width())
        height = max(100, canvas.winfo_height())
        px_per_m = 12.0
        center_x, center_y = width / 2, height / 2
        camera_x, camera_y = self.flight.x, self.flight.y
        grid_x, grid_y = math.floor(camera_x / 5), math.floor(camera_y / 5)
        for x in range(grid_x - 8, grid_x + 9):
            screen_x = center_x + (x * 5 - camera_x) * px_per_m
            canvas.create_line(screen_x, 0, screen_x, height, fill="#e2e8f0")
        for y in range(grid_y - 8, grid_y + 9):
            screen_y = center_y - (y * 5 - camera_y) * px_per_m
            canvas.create_line(0, screen_y, width, screen_y, fill="#e2e8f0")
        origin_x = center_x - camera_x * px_per_m
        origin_y = center_y + camera_y * px_per_m
        room = (self.flight.room_half_size - .75) * px_per_m
        canvas.create_rectangle(origin_x - room, origin_y - room, origin_x + room, origin_y + room,
                                outline=RED if self.flight.boundary_stop else "#94a3b8", dash=(5, 4), width=2)
        canvas.create_oval(origin_x - 4, origin_y - 4, origin_x + 4, origin_y + 4, fill=AMBER, outline="")
        canvas.create_text(12, 12, text="N ↑  TRASA LOTU / SYMULACJA", anchor="nw", fill=NEON, font=("Segoe UI", 9, "bold"))
        points = []
        for x, y in self.flight.trail:
            points.extend((center_x + (x - camera_x) * px_per_m, center_y - (y - camera_y) * px_per_m))
        if len(points) >= 4:
            canvas.create_line(*points, fill=AMBER, width=2)
        x = center_x
        y = center_y
        h = self.flight.heading
        # Code-native quadcopter, rotated in heading, plus world velocity vector.
        def rotor(dx, dy):
            return x + math.cos(h) * dx + math.sin(h) * dy, y + math.sin(h) * dx - math.cos(h) * dy
        for dx, dy in ((-16, 16), (16, 16), (-16, -16), (16, -16)):
            rx, ry = rotor(dx, dy)
            canvas.create_line(x, y, rx, ry, fill=NEON, width=3)
            canvas.create_oval(rx - 7, ry - 7, rx + 7, ry + 7, outline=NEON, width=2)
        canvas.create_line(x, y, x + self.flight.vx * px_per_m, y - self.flight.vy * px_per_m, fill=AMBER, arrow="last", width=2)
        nose = (x + math.sin(h) * 17, y - math.cos(h) * 17)
        left = (x - math.cos(h) * 11 - math.sin(h) * 7, y - math.sin(h) * 11 + math.cos(h) * 7)
        right = (x + math.cos(h) * 11 - math.sin(h) * 7, y + math.sin(h) * 11 + math.cos(h) * 7)
        canvas.create_polygon(*nose, *left, *right, fill=NEON, outline=WHITE, width=2)
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=WHITE, outline="")
        speed = math.hypot(self.flight.vx, self.flight.vy)
        self.flight_data.configure(text=f"DRON SYMULOWANY  X {self.flight.x:+.1f} m  Y {self.flight.y:+.1f} m  H {self.flight.z:.1f} m  V {speed:.1f} m/s  HDG {math.degrees(h):.0f}°")

    def tick(self):
        # Direct test invocations and the timer must not create parallel loops.
        if self.tick_job is not None:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        now = time.monotonic()
        for event in self.video.poll():
            self.video_status.set("WIDEO: " + event[:150])
            if "fps" not in event.lower():
                self.log("WIDEO: " + event[:180])
        sim_dt = now - self.last_sim_step
        self.last_sim_step = now
        if sim_dt >= .3 and (self.reader is not None or self.link is not None or self.demo_started is not None):
            self.stop()
            self.log("Przerwa pętli ≥300 ms — wymagane ręczne wznowienie.")
        if self.reader is None and not self.stop_latched and now >= self.next_retry:
            self.next_retry = now + 2.0
            self.connect_selected(quiet=True)
        if self.reader is not None:
            try:
                self.state = self.reader.read()
                self.last_read = now
                self.raw_status.set("RAW: " + "  ".join(f"A{i}={v:+.3f}" for i, v in enumerate(self.state["raw_axes"])))
                self.raw_samples.append(self.state["raw_axes"])
                for name in AXES:
                    self.input_labels[name].set(f"{self.state[name]:.3f}")
                    self.draw_bar(self.input_bars[name], self.state[name], AMBER if name == "brake" else NEON, name == "steering")
                if self.calibration is not None:
                    self.calibration_step(self.state)
                    self.neutral()
                else:
                    command = map_state(self.state, self.config, self.profile.get())
                    self.output = self.limiter.apply(command, sim_dt, min(.35, self.limit.get())) if self.cautious.get() else command
            except (pygame.error, RuntimeError, OSError, ValueError, TypeError, KeyError) as exc:
                self.log(f"UTRATA G29: {exc}")
                self.neutral()
                if self.link:
                    self.link.close()
                    self.link = None
                if self.device is not None:
                    try:
                        self.device.quit()
                    except pygame.error:
                        pass
                self.device = None
                self.reader = None
                self.clear_inputs()
                self.calibration = None
                self.output = {name: 0.0 for name in self.output}
                self.status.set("G29 ODŁĄCZONY / WYJŚCIA ZERO")
                self.stop_latched = True
                self.help_status.set("Utrata wejścia. Kliknij POŁĄCZ G29, aby świadomie wznowić odczyt.")
                self.next_retry = now + 2.0
        if self.demo_started is not None:
            elapsed = now - self.demo_started
            self.output = self.demo_command(elapsed)
            if elapsed >= 12.0:
                self.demo_started = None
                self.help_status.set("Demo zakończone. RESET SYMULACJI zeruje trasę.")
                self.log("DEMO ZAKOŃCZONE")
        if self.link is not None and self.demo_started is None:
            was_connected = self.link.connected
            if self.link.accept_once():
                self.log("Telefon: TCP otwarte / czekam na potwierdzenie ACK")
            self.link.poll()
            if was_connected and not self.link.connected:
                self.log(self.link.reason)
                self.inputs_enabled.set(False)
                self.limiter.reset()
                self.output = dict.fromkeys(self.output, 0.0)
                self.help_status.set("Utrata sesji telefonu. Ponownie potwierdź sesję i ręcznie włącz kanały testowe.")
            active = self.inputs_enabled.get() and self.reader is not None and not self.stop_latched and self.calibration is None and self.link.healthy
            packet = {"timestampMs": int(time.time() * 1000), "seq": self.seq, "output": self.output if active else dict.fromkeys(self.output, 0.0),
                      "heartbeat": True, "inputConnected": active, "emergency": self.stop_latched}
            if self.link.send(packet):
                self.last_tx = now
                self.sent_window += 1
            elif was_connected and not self.link.connected:
                self.inputs_enabled.set(False)
            self.seq += 1
        if now - self.rate_start >= 1.0:
            self.sent_rate = round(self.sent_window / (now - self.rate_start))
            self.sent_window = 0
            self.rate_start = now
        if self.link is None:
            self.link_status.set("ANDROID: LINK WYŁĄCZONY")
        elif self.link.healthy:
            dji = self.link.remote.get("dji", {})
            if not isinstance(dji, dict):
                dji = {}
            suffix = "SDK: ODCZYT (NIEZWERYF.)" if dji.get("telemetryFresh") is True else "DRON: BRAK TELEMETRII"
            self.link_status.set("ACK OK / " + suffix)
        elif self.link.connected:
            self.link_status.set("TELEFON: TCP / OCZEKIWANIE NA ACK")
        else:
            self.link_status.set("TELEFON: " + self.link.reason[:48])
        ack_age = (now - self.link.last_ack) * 1000 if self.link and self.link.last_ack else math.inf
        report = safety_summary(diagnostics_view(self.link.remote if self.link else {}, ack_age), self.stop_latched)
        self.safety_status.set("Sterowanie lotem wyłączone • brak ochrony przed ścianami\n" + "  |  ".join(report["alerts"][:3]))
        if report["criticalBattery"]:
            self.inputs_enabled.set(False)
            self.neutral()
        age = f"{int((now - self.last_tx) * 1000)} ms" if self.last_tx else "--"
        if self.link and self.link.healthy:
            usb = self.link.remote.get("usb", {})
            detected = len(usb.get("devices", [])) + len(usb.get("accessories", [])) if isinstance(usb, dict) else 0
            details = f"RTT: {self.link.rtt_ms:.0f} ms | średnia {self.link.average_rtt:.0f} ms | ACK 300 ms\nUSB deskryptory: {detected} | MODE: {self.link.remote.get('mode', '?')}"
        else:
            details = "BRAK ACK / polecenia do telefonu neutralne\nUSB i TCP nie potwierdzają połączenia radiowego z dronem"
        self.metrics.configure(text=f"TX: {self.sent_rate}/s | OSTATNIA: {age}\n{details}")
        self.led.itemconfigure(self.led_circle, fill=NEON if self.link and self.link.healthy and int(now * 4) % 2 else (AMBER if self.reader else RED))
        for name in self.output:
            self.output_labels[name].set(f"{self.output[name]:+.3f}")
            self.draw_bar(self.channel_bars[name], self.output[name], NEON, True)
        self.flight.step(self.output, sim_dt)
        self.draw_horizon()
        self.draw_flight_map()
        delay = max(15, round(1000 / max(20, min(50, int(self.config.get("updateRate", 40))))))
        self.tick_job = self.root.after(delay, self.tick)

    def close(self):
        if self.tick_job is not None:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        self.video.close()
        if self.dji_panel and not self.dji_panel.closed:
            self.dji_panel.close()
        if self.connection_panel and not self.connection_panel.closed:
            self.connection_panel.close()
        self.stop()
        pygame.quit()
        self.root.destroy()

    def open_dji_panel(self):
        if self.dji_panel and not self.dji_panel.closed:
            self.dji_panel.window.lift()
        else:
            self.dji_panel = DjiTelemetryPanel(self)


def main():
    root = tk.Tk()
    if "--self-test" in sys.argv:
        root.withdraw()
        app = None
        result = {"version": "V5-OPERATOR-READONLY", "ok": False}
        try:
            app = Cockpit(root)
            app.connect_selected(quiet=True)
            sample = app.reader.read() if app.reader else None
            result.update(ok=True, pygame=pygame.version.ver, sdl=list(pygame.get_sdl_version()),
                          g29Detected=sample is not None, rawAxes=sample.get("raw_axes", []) if sample else [],
                          videoPlayer=str(app.video.executable()), protocolVersion=2, flightControl=False, collisionAvoidance=False)
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            if app: app.close()
            else: root.destroy()
        (APP_DIR / "self-test.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        raise SystemExit(0 if result["ok"] else 1)
    Cockpit(root)
    root.mainloop()


if __name__ == "__main__":
    main()
