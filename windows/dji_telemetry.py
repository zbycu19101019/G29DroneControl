"""Strict, read-only view of SDK diagnostics, separate from the simulator."""
from __future__ import annotations

import json
import math
import time
import tkinter as tk


def diagnostics_view(remote: dict, ack_age_ms: float) -> dict:
    """Never infer aircraft support/flight authority from USB, TCP, or an SDK key."""
    dji = remote.get("dji", {}) if isinstance(remote, dict) else {}
    if not isinstance(dji, dict):
        dji = {}
    result = {key: dji.get(key, "--") for key in (
        "registration", "connection", "model", "productConnected", "rcConnected",
        "flightControllerConnected", "telemetryAgeMs", "batteryAgeMs", "usbPermission", "error")}
    link_live = math.isfinite(ack_age_ms) and 0 <= ack_age_ms < 300
    age = dji.get("telemetryAgeMs")
    fresh = (link_live and dji.get("connection") == "READ_ONLY" and dji.get("telemetryFresh") is True
             and dji.get("productConnected") is True
             and dji.get("flightControllerConnected") is True
             and isinstance(age, (int, float)) and not isinstance(age, bool)
             and math.isfinite(age) and age >= 0 and age + ack_age_ms <= 1500)
    telemetry = dji.get("telemetry")
    if not isinstance(telemetry, dict) or telemetry.get("source") != "DJI_MSDK_FLIGHT_CALLBACK":
        fresh = False
    clean = {}
    if fresh:
        for name in ("pitch", "roll", "yaw", "altitudeM", "velocityXMps", "velocityYMps", "velocityZMps", "satellites"):
            value = telemetry.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                clean[name] = value
        for name in ("flying", "motorsOn"):
            if isinstance(telemetry.get(name), bool):
                clean[name] = telemetry[name]
        if isinstance(telemetry.get("flightMode"), str):
            clean["flightMode"] = telemetry["flightMode"][:60]
    result.update(linkLive=link_live, telemetryFresh=fresh, telemetry=clean if fresh else None,
                  flightControl=False, officialMini2SeSupport=False,
                  validation="ODCZYT SDK — NIEZWERYFIKOWANY NA TYM DRONIE")
    battery_age = dji.get("batteryAgeMs")
    battery = dji.get("battery")
    battery_fresh = (link_live and dji.get("connection") == "READ_ONLY" and dji.get("productConnected") is True and dji.get("batteryFresh") is True and isinstance(battery, dict)
                     and battery.get("source") == "DJI_MSDK_BATTERY_CALLBACK"
                     and isinstance(battery_age, (int, float)) and not isinstance(battery_age, bool)
                     and math.isfinite(battery_age) and battery_age >= 0 and battery_age + ack_age_ms <= 3000)
    result["battery"] = None
    if battery_fresh:
        clean_battery = {}
        for name in ("percent", "temperatureC"):
            value = battery.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                if name != "percent" or 0 <= value <= 100:
                    clean_battery[name] = value
        result["battery"] = clean_battery
    return result


class DjiTelemetryPanel:
    def __init__(self, owner):
        self.owner = owner
        self.closed = False
        self.window = tk.Toplevel(owner.root)
        self.window.title("DJI SDK / DIAGNOSTYKA — TYLKO ODCZYT")
        self.window.geometry("740x620")
        self.window.configure(bg="#f2f5f9")
        tk.Label(self.window, text="DJI / SDK READ ONLY", font=("Segoe UI", 20, "bold"),
                 bg="#f2f5f9", fg="#2563eb").pack(anchor="w", padx=18, pady=14)
        tk.Label(self.window, text="Mini 2 SE: brak oficjalnego wsparcia. Sterowanie lotem ZABLOKOWANE.\n"
                 "Rejestrację i odczyt włącz ręcznie w APK DJI na telefonie.\n"
                 "Test: dron na ziemi, bez śmigieł; zamknij DJI Fly przed odczytem.\n"
                 "Horyzont i mapa głównego okna nadal pokazują WYŁĄCZNIE SYMULACJĘ.",
                 justify="left", wraplength=700, bg="#f2f5f9", fg="#a16207").pack(fill="x", padx=18)
        self.status = tk.StringVar()
        tk.Label(self.window, textvariable=self.status, font=("Segoe UI", 12), bg="#f2f5f9", fg="#142335",
                 anchor="w").pack(fill="x", padx=18, pady=12)
        self.text = tk.Text(self.window, bg="#f8fafc", fg="#2563eb", font=("Segoe UI", 10),
                            wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.poll()

    def poll(self):
        if self.closed:
            return
        link = self.owner.link
        age = (time.monotonic() - link.last_ack) * 1000 if link and link.last_ack else math.inf
        value = diagnostics_view(link.remote if link else {}, age)
        if not value["linkLive"]:
            message = "BRAK ACK — brak bieżącej telemetrii"
        elif value["telemetryFresh"]:
            message = "CALLBACK SDK — świeży odczyt; zgodność z dronem niezweryfikowana"
        else:
            message = "BRAK ŚWIEŻYCH DANYCH LOTU — USB/klucz nie potwierdzają telemetrii"
        self.status.set(message)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", json.dumps(value, ensure_ascii=False, indent=2))
        self.text.configure(state="disabled")
        self.poll_job = self.window.after(200, self.poll)

    def close(self):
        self.closed = True
        self.window.after_cancel(self.poll_job)
        self.window.destroy()
