"""Offline validation and optional full three-system integration."""
import asyncio
import importlib.util
import unittest

from scripts.demo_trinity_v03 import validate_snapshot


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "source": "opcua_explicit_local_read", "signals": [
                {"signal_id": "temperature", "quality": "good", "value": 42.0,
                 "source_timestamp": "2026-01-01T00:00:00+00:00"}
            ]
        }

    def test_converts_verified_timestamp_to_int64(self):
        rows, vals = validate_snapshot(self.snapshot, ("temperature",))
        self.assertEqual(vals, [42.0])
        self.assertEqual(rows[0]["time_ms"], 1767225600000)

    def test_rejects_forged_source(self):
        self.snapshot["source"] = "remote"
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, ("temperature",))

    def test_rejects_bad_quality_or_nonfinite(self):
        for quality, value in (("bad_status", 42.0), ("good", float("nan")), ("good", True)):
            with self.subTest(quality=quality, value=value):
                self.snapshot["signals"][0].update(quality=quality, value=value)
                with self.assertRaises(ValueError):
                    validate_snapshot(self.snapshot, ("temperature",))

    def test_rejects_missing_timestamp_and_mismatch(self):
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, ("other",))
        self.snapshot["signals"][0]["source_timestamp"] = None
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, ("temperature",))


HAS_EXTRAS = all(importlib.util.find_spec(x) for x in ("asyncua", "pyarrow", "onnx", "onnxruntime", "numpy"))


@unittest.skipUnless(HAS_EXTRAS, "integration extras unavailable")
class ActualIntegrationTests(unittest.TestCase):
    def test_local_opcua_arrow_onnx_roundtrip(self):
        from scripts.demo_trinity_v03 import run_demo
        report = asyncio.run(run_demo())
        self.assertTrue(report["arrow_roundtrip_valid"])
        self.assertTrue(report["compute_correctness"]["passed"])
        self.assertEqual(report["validated_sensor_values"], [42.0, 1800.0, 12.34])
        self.assertEqual(len(report["pipeline"]), 4)
