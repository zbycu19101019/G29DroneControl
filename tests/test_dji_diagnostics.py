import math
from pathlib import Path
import tkinter as tk
import unittest
from unittest.mock import patch

from windows.dji_telemetry import DjiTelemetryPanel, diagnostics_view


def fixture():
    return {"dji": {"registration": "REGISTERED", "connection": "READ_ONLY",
                    "productConnected": True, "flightControllerConnected": True,
                    "telemetryFresh": True, "telemetryAgeMs": 50,
                    "telemetry": {"source": "DJI_MSDK_FLIGHT_CALLBACK", "yaw": 12.5, "pitch": 2,
                                  "roll": -1, "altitudeM": 0, "satellites": 0, "motorsOn": False}}}


class DjiDiagnosticsTests(unittest.TestCase):
    def test_fresh_callbacks_are_not_flight_authority(self):
        view = diagnostics_view(fixture(), 20)
        self.assertTrue(view["telemetryFresh"])
        self.assertEqual(view["telemetry"]["yaw"], 12.5)
        self.assertFalse(view["flightControl"])
        self.assertFalse(view["officialMini2SeSupport"])

    def test_no_ack_stale_data_and_missing_fc_never_display_telemetry(self):
        for age in (300, 500, math.inf, math.nan, -1):
            self.assertIsNone(diagnostics_view(fixture(), age)["telemetry"])
        for change in ({"telemetryAgeMs": 1490}, {"telemetryAgeMs": -1}, {"telemetryAgeMs": math.nan},
                       {"telemetryFresh": False}, {"productConnected": False}, {"flightControllerConnected": False}):
            value = fixture(); value["dji"].update(change)
            self.assertIsNone(diagnostics_view(value, 20)["telemetry"])

    def test_usb_and_fake_numeric_strings_do_not_count_as_data(self):
        self.assertIsNone(diagnostics_view({"usb": {"accessories": ["RC-N1"]}}, 10)["telemetry"])
        value = fixture(); value["dji"]["telemetry"].update(yaw="12", pitch=math.nan, roll=True)
        view = diagnostics_view(value, 10)
        self.assertNotIn("yaw", view["telemetry"])
        self.assertNotIn("pitch", view["telemetry"])
        self.assertNotIn("roll", view["telemetry"])

    def test_old_battery_is_hidden(self):
        value = fixture(); value["dji"].update(batteryFresh=True, batteryAgeMs=2990,
            battery={"source": "DJI_MSDK_BATTERY_CALLBACK", "percent": 80})
        self.assertIsNone(diagnostics_view(value, 20)["battery"])
        value["dji"]["batteryAgeMs"] = 100
        self.assertEqual(diagnostics_view(value, 20)["battery"], {"percent": 80})

    def test_module_contains_no_flight_camera_or_config_write_calls(self):
        root = Path(__file__).resolve().parents[1] / "android/app/src/dji/java"
        source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.*"))
        for method in ("sendVirtualStickFlightControlData(", "setVirtualStickModeEnabled(", "startTakeoff(",
                       "startLanding(", "turnOnMotors(", "turnOffMotors(", "startGoHome(", "setMaxFlightHeight(",
                       "startShootPhoto(", "startRecordVideo(", "setHomeLocation("):
            self.assertNotIn(method, source)

    def test_panel_disconnect_clears_values_and_closes(self):
        root = tk.Tk(); root.withdraw()
        class Owner:
            link = None
        owner = Owner(); owner.root = root
        panel = DjiTelemetryPanel(owner)
        try:
            self.assertIn("BRAK ACK", panel.status.get())
            self.assertIn('"telemetry": null', panel.text.get("1.0", "end"))
        finally:
            panel.close(); root.destroy()
        self.assertTrue(panel.closed)


if __name__ == "__main__": unittest.main()
