import json
import socketserver
import struct
import threading
import unittest
from pathlib import Path

from trinitylab.industrial.core import (benchmark, drift, load_profile,
                                        load_registers, parse_profile, snapshot)
from trinitylab.industrial.modbus import ModbusError, read_registers

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "industrial"


class IndustrialTests(unittest.TestCase):
    def setUp(self):
        self.p1 = load_profile(ROOT / "profile_v1.json")
        self.p2 = load_profile(ROOT / "profile_v2.json")
        self.regs = load_registers(ROOT / "registers.json")

    def test_fixture_decoding(self):
        r = snapshot(self.p1, self.regs)
        self.assertEqual(r["signals"][0]["value"], 42)
        self.assertEqual(r["signals"][2]["value"], 12.34)
        self.assertTrue(all(x["quality"] == "good" for x in r["signals"]))

    def test_missing_and_out_of_range(self):
        vals = {100: 65535}
        r = snapshot(self.p1, vals)
        self.assertEqual(r["signals"][0]["quality"], "out_of_range")
        self.assertEqual(r["signals"][1]["quality"], "missing")

    def test_drift_discovery(self):
        r = drift(self.p1, self.p2)
        self.assertTrue(r["drift_detected"])
        changed = {x["signal_id"]: x for x in r["changes"]}
        self.assertIn("address", changed["motor_temperature"]["fields"])
        self.assertIn("scale", changed["line_pressure"]["fields"])
        self.assertEqual(changed["flow_rate"]["type"], "added")

    def test_invalid_version_comparison(self):
        with self.assertRaises(ValueError):
            drift(self.p2, self.p1)

    def test_duplicate_signal_rejected(self):
        raw = json.loads((ROOT / "profile_v1.json").read_text())
        raw["signals"].append(raw["signals"][0])
        with self.assertRaises(ValueError):
            parse_profile(raw)

    def test_untrusted_fields_rejected(self):
        raw = json.loads((ROOT / "profile_v1.json").read_text())
        raw["signals"][0]["scale"] = "bad"
        with self.assertRaises(ValueError):
            parse_profile(raw)
        raw["signals"][0]["scale"] = True
        with self.assertRaises(ValueError):
            parse_profile(raw)

    def test_simulated_benchmark(self):
        r = benchmark(self.p1, self.regs, 4)
        self.assertEqual(r["quality_counts"]["good"], 3)
        self.assertEqual(r["scenario"], "in_memory_snapshot_only")


class _ModbusHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = bytearray()
        while len(data) < 12:
            chunk = self.request.recv(12 - len(data))
            if not chunk:
                return
            data.extend(chunk)
        tx, protocol, length, unit, function, address, count = struct.unpack(">HHHBBHH", data)
        assert protocol == 0 and length == 6 and function in (3, 4)
        values = [12 + address + n for n in range(count)]
        response = struct.pack(">HHHBBB", tx, 0, 3 + 2 * count, unit, function, 2 * count)
        response += struct.pack(">" + "H" * count, *values)
        if getattr(self.server, "malformed", False):
            response = bytes([response[0] ^ 1]) + response[1:]
        self.request.sendall(response[:5])
        self.request.sendall(response[5:])


class _LocalServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ModbusSafetyTests(unittest.TestCase):
    def test_default_does_not_connect(self):
        with self.assertRaises(PermissionError):
            read_registers("127.0.0.1", 15020, 0, 1)

    def test_range_validation(self):
        with self.assertRaises(ValueError):
            read_registers("127.0.0.1", 15020, 65535, 2, enable_network=True)
        with self.assertRaises(ValueError):
            read_registers("127.0.0.1", 15020, 0, 126, enable_network=True)
        with self.assertRaises(ValueError):
            read_registers("127.0.0.1", 15020, 0, 1, kind="write", enable_network=True)

    def test_remote_rejected_without_two_flags(self):
        with self.assertRaises(PermissionError):
            read_registers("192.0.2.1", 15020, 0, 1, enable_network=True)

    def _server(self, malformed=False):
        server = _LocalServer(("127.0.0.1", 0), _ModbusHandler)
        server.malformed = malformed
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_loopback_read_only_fc03(self):
        server = self._server()
        result = read_registers("127.0.0.1", server.server_address[1], 100, 3, enable_network=True)
        self.assertEqual(result, [112, 113, 114])

    def test_loopback_input_fc04(self):
        server = self._server()
        result = read_registers("127.0.0.1", server.server_address[1], 10, 2, kind="input", enable_network=True)
        self.assertEqual(result, [22, 23])

    def test_rejects_header_corruption(self):
        server = self._server(malformed=True)
        with self.assertRaises(ModbusError):
            read_registers("127.0.0.1", server.server_address[1], 0, 1, enable_network=True)
