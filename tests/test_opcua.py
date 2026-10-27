"""Network-off unit cases and opt-in integration coverage for read-only OPC UA."""
import asyncio
import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from trinitylab.industrial.opcua import (
    OPCUAError, evaluate_datavalue, load_opcua_profile, opcua_profile_drift,
    parse_opcua_profile, read_opcua_snapshot, validate_lab_endpoint,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures/industrial"


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_opcua_profile(FIX / "opcua_profile_v1.json")
        self.raw = json.loads((FIX / "opcua_profile_v1.json").read_text())

    def test_profile_drift(self):
        v2 = load_opcua_profile(FIX / "opcua_profile_v2.json")
        result = opcua_profile_drift(self.profile, v2)
        self.assertTrue(result["drift_detected"])
        by_id = {c.get("signal_id"): c for c in result["changes"]}
        self.assertIn("identifier", by_id["motor_temperature"]["fields"])
        self.assertIn("scale", by_id["line_pressure"]["fields"])
        self.assertEqual(by_id["motor_current"]["type"], "added")

    def test_rejects_invalid_profile_versions_and_duplicate_nodes(self):
        for version in (True, 0, "2"):
            raw = copy.deepcopy(self.raw)
            raw["version"] = version
            with self.assertRaises(ValueError):
                parse_opcua_profile(raw)
        raw = copy.deepcopy(self.raw)
        raw["signals"][1]["identifier"] = raw["signals"][0]["identifier"]
        with self.assertRaises(ValueError):
            parse_opcua_profile(raw)

    def test_rejects_malformed_node_identifiers_and_scalars(self):
        for field, value in (("identifier", "ns=1;i=2"), ("identifier", "\nBad"),
                             ("scale", float("nan")), ("minimum", True),
                             ("unit", "x\n")):
            raw = copy.deepcopy(self.raw)
            raw["signals"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                parse_opcua_profile(raw)

    def test_drift_rejects_mismatch(self):
        with self.assertRaises(ValueError):
            opcua_profile_drift(self.profile, self.profile)

    def test_strict_loopback_only(self):
        self.assertEqual(validate_lab_endpoint("opc.tcp://127.0.0.1:4840/"),
                         "opc.tcp://127.0.0.1:4840/")
        for endpoint in ("opc.tcp://localhost:4840/", "opc.tcp://192.0.2.1:4840/",
                         "opc.tcp://127.0.0.2:4840/", "opc.tcp://evil.test:4840/",
                         "opc.tcp://user@127.0.0.1:4840/", "http://127.0.0.1:4840/",
                         "opc.tcp://127.0.0.1:4840/?a=b", "opc.tcp://127.0.0.1:0/"):
            with self.subTest(endpoint=endpoint), self.assertRaises((PermissionError, ValueError)):
                validate_lab_endpoint(endpoint)

    def test_disabled_by_default_even_if_library_missing(self):
        with self.assertRaises(PermissionError):
            asyncio.run(read_opcua_snapshot(self.profile, "opc.tcp://127.0.0.1:4840/"))
        with self.assertRaises(PermissionError):
            asyncio.run(read_opcua_snapshot(self.profile, "opc.tcp://example.com:4840/", enable_network=True))

    def test_status_and_type_validation(self):
        signal = self.profile.signals[0]
        def make(value, good=True, stamp=None):
            return SimpleNamespace(StatusCode=SimpleNamespace(is_good=lambda: good),
                                   Value=SimpleNamespace(Value=value), SourceTimestamp=stamp)
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record = evaluate_datavalue(signal, make(42.0, stamp=stamp))
        self.assertEqual(record["quality"], "good")
        self.assertEqual(record["source_timestamp"], stamp.isoformat())
        self.assertEqual(evaluate_datavalue(signal, make(10, good=False))["quality"], "bad_status")
        self.assertEqual(evaluate_datavalue(signal, make("42"))["quality"], "invalid_type")
        self.assertEqual(evaluate_datavalue(signal, make(float("nan")))["quality"], "invalid_type")
        self.assertEqual(evaluate_datavalue(signal, make(True))["quality"], "invalid_type")
        self.assertEqual(evaluate_datavalue(signal, make(10000))["quality"], "out_of_range")
        self.assertEqual(evaluate_datavalue(signal, None)["quality"], "missing")

    def test_bounds_and_exception_mapping(self):
        with self.assertRaises(ValueError):
            asyncio.run(read_opcua_snapshot(self.profile, "opc.tcp://127.0.0.1:4840/",
                                            enable_network=True, timeout=11))


try:
    import asyncua  # noqa: F401
except ImportError:
    HAS_ASYNCUA = False
else:
    HAS_ASYNCUA = True


@unittest.skipUnless(HAS_ASYNCUA, "asyncua optional extra not installed")
class LoopbackIntegrationTests(unittest.TestCase):
    def test_local_server_reconnect_and_mapping(self):
        from scripts.demo_opcua_loopback import run_demo
        report = asyncio.run(run_demo())
        self.assertEqual(report["scenario"], "local_opcua_read_only")
        self.assertTrue(report["fresh_session_again"])
        self.assertTrue(report["profile_drift"]["drift_detected"])

    def test_rejects_unavailable_server_with_bounded_error(self):
        # Never access a non-loopback endpoint; pre-reserve a closed ephemeral port.
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        profile = load_opcua_profile(FIX / "opcua_profile_v1.json")
        with self.assertRaises(OPCUAError):
            asyncio.run(read_opcua_snapshot(profile, f"opc.tcp://127.0.0.1:{port}/trinity/",
                                            enable_network=True, timeout=0.5))
