import json
import math
import socket
import time
import unittest
from unittest.mock import patch

from cockpit import default_config
from windows.adb_link import AdbLink
from windows.bridge_link import JsonLineServer
from windows.configuration import validate_config
from windows.control_mapping import PROFILES, map_state
from windows.driver import axis_value
from windows.simulator import FlightModel
from windows.video_link import ScreenViewer
from windows.signed_frames import VERSION, encode_signed, decode_signed
from pathlib import Path


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.config = default_config()

    def test_released_pedals_are_zero_in_both_directions(self):
        for rest, pressed in ((1, -1), (-1, 1)):
            self.config["calibration"] = {"throttle": {"rest": rest, "pressed": pressed}}
            for inverted in (True, False):
                self.config["axisInverted"]["throttle"] = inverted
                self.assertEqual(axis_value(rest, "throttle", self.config), 0)
                self.assertEqual(axis_value(pressed, "throttle", self.config), 1)

    def test_uncalibrated_pedal_never_accelerates(self):
        for value in (-1, 0, 1):
            self.assertEqual(axis_value(value, "throttle", self.config), 0)

    def test_steering_direction_center_and_deadzone(self):
        self.assertEqual(axis_value(.01, "steering", self.config), 0)
        self.assertEqual(axis_value(-1, "steering", self.config), -1)
        self.assertEqual(axis_value(1, "steering", self.config), 1)

    def test_nonfinite_axis_rejected(self):
        with self.assertRaises(RuntimeError): axis_value(math.nan, "steering", self.config)
        with self.assertRaises(RuntimeError): map_state({"steering": math.inf}, self.config)

    def test_all_profiles_bounded(self):
        for profile in PROFILES:
            output = map_state({"steering": 1, "throttle": 1, "brake": 0, "paddle_right": True}, self.config, profile)
            self.assertGreater(output["yaw"], 0)
            self.assertTrue(all(-.6 <= value <= .6 for value in output.values()))

    def test_simulator_ground_and_takeoff(self):
        flight = FlightModel()
        for _ in range(40): flight.step({"pitch": 1}, .025)
        self.assertEqual(flight.x, 0); self.assertEqual(flight.y, 0)
        for _ in range(40): flight.step({"vertical": .5, "pitch": .5}, .025)
        self.assertGreater(flight.z, 0); self.assertGreater(flight.y, 0)

    def test_config_rejects_nan_and_duplicate_axes(self):
        self.config["deadzone"] = math.nan
        with self.assertRaises(ValueError): validate_config(self.config)
        self.config = default_config(); self.config["axisMap"]["brake"] = 1
        with self.assertRaises(ValueError): validate_config(self.config)

    def test_config_clamps_limits(self):
        self.config["outputLimit"] = 3; self.config["updateRate"] = 900
        validate_config(self.config)
        self.assertEqual(self.config["outputLimit"], 1); self.assertEqual(self.config["updateRate"], 50)

    def test_adb_arguments_are_validated(self):
        for address in ("host;command:12", "192.168.1.1:99999", "no-port"):
            with self.assertRaises(RuntimeError): AdbLink.validate_address(address)
        AdbLink.validate_address("198.51.100.10:44757")

    def test_video_is_read_only_without_recording(self):
        args = ScreenViewer.arguments(Path("scrcpy.exe"), "test-phone")
        self.assertIn("--no-control", args); self.assertIn("--no-audio", args)
        self.assertIn("--no-clipboard-autosync", args)
        self.assertFalse(any(arg.startswith("--record") or "otg" in arg for arg in args))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.server = JsonLineServer(port=0); self.server.start()
        self.peer = socket.create_connection(self.server.server.getsockname(), timeout=1)
        self.peer.settimeout(1)
        self.assertTrue(self.server.accept_once())
        self.nonce = "b" * 32
        self.peer.sendall(encode_signed({"version": VERSION, "type": "hello", "clientNonce": self.nonce}, self.server.pairing_token))
        self.server.poll()

    def tearDown(self):
        self.peer.close(); self.server.close()

    def send(self, seq=1):
        self.assertTrue(self.server.send({"seq": seq, "output": dict.fromkeys(("yaw", "pitch", "roll", "vertical"), 0.0), "heartbeat": True}))
        packet = decode_signed(self.peer.recv(8192), self.server.pairing_token)
        self.assertFalse(packet["inputConnected"])
        return packet

    def ack(self, seq=1, session=None):
        return encode_signed({"version": VERSION, "type": "ack", "seq": seq, "clientNonce": self.nonce,
                              "sessionId": session or self.server.session, "mode": "MOCK_ONLY", "flightControl": False}, self.server.pairing_token)

    def test_handshake_and_ack(self):
        self.assertFalse(self.server.healthy); self.send()
        self.peer.sendall(self.ack()); self.server.poll()
        self.assertTrue(self.server.healthy); self.assertGreaterEqual(self.server.rtt_ms, 0)

    def test_fragmented_ack(self):
        self.send(); frame = self.ack()
        self.peer.sendall(frame[:10]); self.server.poll(); self.assertFalse(self.server.healthy)
        self.peer.sendall(frame[10:]); self.server.poll(); self.assertTrue(self.server.healthy)

    def test_wrong_session_disconnects(self):
        self.send(); self.peer.sendall(self.ack(session="old")); self.server.poll()
        self.assertFalse(self.server.connected)

    def test_duplicate_ack_does_not_refresh_watchdog(self):
        self.send(); self.peer.sendall(self.ack()); self.server.poll(); last = self.server.last_ack
        self.peer.sendall(self.ack()); self.server.poll(); self.assertEqual(last, self.server.last_ack)

    def test_timeout_disconnects(self):
        self.server.accepted_at -= .31; self.server.poll(); self.assertFalse(self.server.connected)

    def test_delayed_ack_disconnects(self):
        self.send(); self.server.pending[1] -= .31
        self.peer.sendall(self.ack()); self.server.poll(); self.assertFalse(self.server.connected)

    def test_eof_disconnects(self):
        self.peer.shutdown(socket.SHUT_WR); self.server.poll(); self.assertFalse(self.server.connected)

    def test_bad_json_disconnects(self):
        self.peer.sendall(b"garbage\n"); self.server.poll(); self.assertFalse(self.server.connected)

    def test_nan_output_not_sent(self):
        self.assertFalse(self.server.send({"seq": 1, "output": {"yaw": math.nan}}))
        self.assertFalse(self.server.connected)

    def test_close_releases_port(self):
        port = self.server.server.getsockname()[1]; self.server.close()
        with socket.socket() as probe: probe.bind(("127.0.0.1", port))


class CockpitTests(unittest.TestCase):
    def test_live_input_ack_gate_stop_and_latch(self):
        import tkinter as tk
        from cockpit import Cockpit
        root = tk.Tk(); root.withdraw()
        with patch("cockpit.merged_config", return_value=default_config()), patch("cockpit.init_pygame"), patch("cockpit.list_devices", return_value=[]):
            app = Cockpit(root)
        root.deiconify(); root.update()
        self.assertGreaterEqual(app.metrics.winfo_rooty(), root.winfo_rooty())
        self.assertLess(app.metrics.winfo_rooty(), root.winfo_rooty() + root.winfo_height())
        state = {"steering": 1, "throttle": 0, "brake": 0, "clutch": 0, "raw_axes": [1, 1, 1, 1]}
        class Reader:
            def read(self): return state
        class Device:
            def quit(self): pass
        app.reader = Reader(); app.device = Device()
        app.inputs_enabled.set(True)
        app.link = JsonLineServer(port=0); app.link.start()
        peer = socket.create_connection(app.link.server.getsockname(), timeout=1)
        nonce = "b" * 32
        peer.sendall(encode_signed({"version": VERSION, "type": "hello", "clientNonce": nonce}, app.link.pairing_token))
        try:
            app.tick(); first = decode_signed(peer.recv(8192), app.link.pairing_token)
            self.assertIn("A0=+1.000", app.raw_status.get())
            self.assertGreater(app.output["yaw"], 0)
            self.assertEqual(first["output"]["yaw"], 0)  # no ACK yet
            ack = {"version": VERSION, "type": "ack", "seq": first["seq"], "sessionId": first["sessionId"], "clientNonce": nonce, "mode": "MOCK_ONLY", "usb": {}, "flightControl": False}
            peer.sendall(encode_signed(ack, app.link.pairing_token))
            app.tick(); active = decode_signed(peer.recv(8192), app.link.pairing_token)
            self.assertGreater(active["output"]["yaw"], 0)
            token = app.link.pairing_token
            app.stop(); last = decode_signed(peer.recv(8192), token)
            self.assertEqual(last["output"]["yaw"], 0); self.assertTrue(last["emergency"])
            self.assertTrue(app.stop_latched); self.assertIsNone(app.reader)
            app.tick(); self.assertEqual(app.output["yaw"], 0)
        finally:
            peer.close()
            if app.link: app.link.close()
            app.close()


if __name__ == "__main__": unittest.main()
