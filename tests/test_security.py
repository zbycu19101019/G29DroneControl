import json
import math
import socket
import unittest
from windows.signed_frames import encode_signed, decode_signed, pairing_code
from windows.safety import InputLimiter, safety_summary
from windows.bridge_link import JsonLineServer
from windows.simulator import FlightModel
from windows.configuration import validate_config
from cockpit import default_config
import tests.test_audit as audit_fixtures
from unittest.mock import patch


class SignedFramesTests(unittest.TestCase):
    token = "00" * 32
    def test_unicode_roundtrip(self):
        packet = {"version": 2, "text": "Świeża bateria", "value": .25}
        self.assertEqual(decode_signed(encode_signed(packet, self.token), self.token), packet)
        self.assertEqual(pairing_code(self.token), "66687AAD")

    def test_wrong_key_and_tampering(self):
        frame = encode_signed({"version": 2, "value": .25}, self.token)
        for value, key in ((frame, "01" * 32), (frame.replace(b"0.25", b"0.75"), self.token)):
            with self.assertRaises(ValueError): decode_signed(value, key)

    def test_strict_envelope(self):
        envelope = json.loads(encode_signed({"version": 2}, self.token))
        for change in ({"version": True}, {"version": 1}, {"payload": []}, {"mac": "00"}, {"extra": 1}):
            altered = dict(envelope, **change)
            with self.assertRaises(ValueError): decode_signed(json.dumps(altered), self.token)

    def test_no_legacy_fallback(self):
        with self.assertRaises(ValueError): decode_signed('{"version":1,"type":"ack"}', self.token)

    def test_bind_localhost_only(self):
        for host in ("0.0.0.0", "localhost", "198.51.100.10"):
            with self.assertRaises(ValueError): JsonLineServer(host=host)

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            decode_signed('{"version":2,"version":2,"payload":"{}","mac":"' + "0" * 64 + '"}', self.token)


class AuthenticatedBridgeTests(unittest.TestCase):
    setUp = audit_fixtures.BridgeTests.setUp
    tearDown = audit_fixtures.BridgeTests.tearDown
    send = audit_fixtures.BridgeTests.send
    ack = audit_fixtures.BridgeTests.ack
    def test_wrong_signature_disconnects(self):
        self.send()
        envelope = json.loads(self.ack()); envelope["mac"] = "00" * 32
        self.peer.sendall((json.dumps(envelope) + "\n").encode()); self.server.poll()
        self.assertFalse(self.server.connected)

    def test_old_nonce_disconnects(self):
        self.send()
        ack = decode_signed(self.ack(), self.server.pairing_token); ack["clientNonce"] = "c" * 32
        self.peer.sendall(encode_signed(ack, self.server.pairing_token)); self.server.poll()
        self.assertFalse(self.server.connected)

    def test_boolean_sequence_not_an_integer(self):
        self.send(); self.peer.sendall(self.ack(seq=True)); self.server.poll()
        self.assertFalse(self.server.connected)

    def test_second_client_cannot_replace_session(self):
        self.send(); self.peer.sendall(self.ack()); self.server.poll()
        session = self.server.session
        with socket.create_connection(self.server.server.getsockname(), timeout=1):
            self.assertFalse(self.server.accept_once())
        self.assertEqual(session, self.server.session); self.assertTrue(self.server.healthy)


class SafetyTests(unittest.TestCase):
    def test_invalid_calibration_and_types_rejected(self):
        for values in ({"min": -1, "center": 1, "max": 0}, {"min": -1, "center": True, "max": 1},
                       {"center": 0}, {"min": -.01, "center": 0, "max": .01}):
            config = default_config(); config["calibration"] = {"steering": values}
            with self.assertRaises(ValueError): validate_config(config)
        for key, value in (("calibration", []), ("buttonMap", {"paddle_left": True}), ("axisInverted", {"steering": 1}),
                           ("deadzone", True), ("calibration", {"throttle": {"rest": 1, "pressed": .99}})):
            config = default_config(); config[key] = value
            with self.assertRaises(ValueError): validate_config(config)

    def test_config_atomic_save_and_no_nan(self):
        import tempfile
        from pathlib import Path
        from windows.driver import save_config, load_config
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            config = default_config(); save_config(path, config)
            self.assertEqual(load_config(path), config)
            before = path.read_bytes()
            config["deadzone"] = math.nan
            with self.assertRaises(ValueError): save_config(path, config)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["config.json"])

    def test_adb_failure_does_not_expose_pairing_key(self):
        from windows.adb_link import AdbLink
        adb = object.__new__(AdbLink)
        token = "ab" * 32
        def response(args, serial="", **kwargs):
            if args == ["get-state"]: return "device"
            if "path" in args: return "package:test.apk"
            if "start" in args: raise RuntimeError("Intent failed " + token)
            return ""
        with patch.object(adb, "run", side_effect=response):
            with self.assertRaises(RuntimeError) as caught: adb.setup("test-phone", 8765, token)
            self.assertNotIn(token, str(caught.exception))

    def test_windows_layout_at_supported_sizes(self):
        import tkinter as tk
        from cockpit import Cockpit
        root = tk.Tk(); root.withdraw()
        try:
            with patch("cockpit.merged_config", return_value=default_config()), patch("cockpit.init_pygame"), patch("cockpit.list_devices", return_value=[]):
                app = Cockpit(root)
            app.stop_latched = True
            root.deiconify()
            for size in ("960x700", "1180x820"):
                root.geometry(size); root.update()
                bottom = root.winfo_rooty() + root.winfo_height()
                self.assertLessEqual(app.metrics.winfo_rooty() + app.metrics.winfo_height(), bottom)
                self.assertGreaterEqual(app.horizon.winfo_height(), 100)
                self.assertGreaterEqual(app.map_canvas.winfo_width(), 100)
                app.draw_horizon(); app.draw_flight_map()
                def children(view):
                    for child in view.winfo_children():
                        yield child; yield from children(child)
                stops = [view for view in children(root) if isinstance(view, tk.Button) and view.cget("text") == "STOP"]
                self.assertEqual(len(stops), 1)
                self.assertLessEqual(stops[0].winfo_rooty() + stops[0].winfo_height(), bottom)
        finally: app.close()

    def test_limiter_caps_and_slew(self):
        limiter = InputLimiter()
        for _ in range(100):
            previous = dict(limiter.last)
            result = limiter.apply(dict.fromkeys(("yaw", "pitch", "roll", "vertical"), 1), .025)
            for name, value in result.items():
                self.assertLessEqual(value, .35)
                self.assertLessEqual(abs(value - previous[name]), .030001)

    def test_pause_and_bad_input_go_neutral(self):
        limiter = InputLimiter(); limiter.apply({"yaw": 1}, .1)
        self.assertTrue(all(v == 0 for v in limiter.apply({"yaw": 1}, .31).values()))
        for bad in (math.nan, math.inf, True):
            with self.assertRaises(RuntimeError): limiter.apply({"yaw": bad}, .025)
            self.assertTrue(all(v == 0 for v in limiter.last.values()))

    def test_never_claim_collision_avoidance_or_flight(self):
        for view in ({}, {"linkLive": True, "telemetryFresh": True, "battery": {"percent": 90}}, {"battery": {"percent": 10}}):
            report = safety_summary(view)
            self.assertFalse(report["flightAllowed"]); self.assertFalse(report["collisionAvoidance"])
        self.assertTrue(safety_summary({"battery": {"percent": 10}})["criticalBattery"])
        self.assertFalse(safety_summary({})["criticalBattery"])

    def test_virtual_room_is_only_simulated_and_bounded(self):
        model = FlightModel(z=2)
        for _ in range(10000): model.step({"pitch": 1, "roll": 1, "vertical": 1}, .1)
        self.assertLessEqual(abs(model.x), 11.25); self.assertLessEqual(abs(model.y), 11.25)
        self.assertEqual(model.z, 5); self.assertTrue(model.boundary_stop)
