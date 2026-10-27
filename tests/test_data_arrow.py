"""Optional PyArrow integration: standard-library tests must remain runnable offline."""
from __future__ import annotations

import gc
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from trinitylab.data import arrow_adapter as arrow
from trinitylab.data.schema import load_schema

ROOT = Path(__file__).resolve().parents[1]
ARROW_AVAILABLE = importlib.util.find_spec("pyarrow") is not None


class AlwaysOfflineArrowTests(unittest.TestCase):
    def test_row_generator_determinism_and_nulls(self):
        a = arrow.generate_rows(32, 42)
        self.assertEqual(a, arrow.generate_rows(32, 42))
        self.assertIsNone(a[0]["reading"])
        self.assertIsNotNone(a[1]["reading"])

    def test_reject_unbounded_workload(self):
        for n in (0, -1, arrow.MAX_ROWS+1, True):
            with self.subTest(n=n), self.assertRaises(ValueError):
                arrow.generate_rows(n)
        with self.assertRaises(ValueError):
            arrow.benchmark(repeats=0)

    def test_reject_bad_schema_rows(self):
        bad = [
            [{"sensor_id": "x", "time_ms": 123, "reading": float("nan")}],
            [{"sensor_id": "x", "time_ms": True, "reading": 1.0}],
            [{"sensor_id": "x", "time_ms": 123, "reading": True}],
            [{"sensor_id": "x", "time_ms": 123, "reading": 1.0, "extra": 2}],
            [{"sensor_id": None, "time_ms": 123, "reading": 1.0}],
        ]
        for obj in bad:
            with self.subTest(obj=obj), self.assertRaises(ValueError):
                arrow.validate_rows(obj)

    def test_json_strict_parity_and_errors(self):
        source = arrow.generate_rows(14)
        self.assertEqual(arrow.json_decode(arrow.json_encode(source)), source)
        for payload in (b"", b"not valid", b'[{"sensor_id":"x","time_ms":1,"reading":NaN}]', b"[]"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                arrow.json_decode(payload)

    def test_evolution_diff_compatibility_is_not_ipc_identity(self):
        folder = ROOT / "fixtures" / "data"
        old = load_schema(folder / "schema_v1.json")
        good = load_schema(folder / "schema_v2_compatible.json")
        bad = load_schema(folder / "schema_v2_breaking.json")
        self.assertTrue(arrow.structural_compatibility(old, good)["compatible"])
        self.assertFalse(arrow.structural_compatibility(old, bad)["compatible"])

    def test_missing_optional_dependency_has_actionable_message(self):
        with patch.object(arrow.importlib, "import_module", side_effect=ImportError("not installed")):
            with self.assertRaisesRegex(RuntimeError, "data-arrow"):
                arrow.require_arrow()

    @unittest.skipIf(ARROW_AVAILABLE, "this CLI check is for an environment without pyarrow")
    def test_no_arrow_cli_returns_actionable_error(self):
        p = subprocess.run([sys.executable, "-m", "trinitylab.data", "arrow-benchmark", "--rows", "2"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("data-arrow", p.stderr)


@unittest.skipUnless(ARROW_AVAILABLE, "optional PyArrow is not installed")
class ArrowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pa = arrow.require_arrow()

    def test_explicit_nullable_schema_and_roundtrip(self):
        source = arrow.generate_rows(25, 3)
        table = arrow.table_from_rows(source)
        self.assertTrue(table.schema.equals(arrow.arrow_schema(), check_metadata=True))
        self.assertEqual(table.column("reading").null_count, 3)
        self.assertEqual(table.num_rows, 25)
        buf = arrow.encode_ipc(table)
        decoded = arrow.decode_ipc(buf)
        self.assertEqual(decoded.to_pylist(), source)
        self.assertEqual(decoded.schema.metadata, arrow.SCHEMA_METADATA)
        self.assertTrue(decoded.equals(table, check_metadata=True))

    def test_reject_corrupted_or_wrong_schema_ipc(self):
        rows = arrow.generate_rows(5)
        table = arrow.table_from_rows(rows)
        with self.assertRaises(ValueError):
            arrow.decode_ipc(b"garbage")
        with self.assertRaises(ValueError):
            arrow.decode_ipc(bytes(arrow.encode_ipc(table))[:12])
        changed = table.replace_schema_metadata({b"trinity.schema_version": b"2"})
        sink = self.pa.BufferOutputStream()
        with self.pa.ipc.new_stream(sink, changed.schema) as writer:
            writer.write_table(changed)
        with self.assertRaisesRegex(ValueError, "schema"):
            arrow.decode_ipc(sink.getvalue())
        with self.assertRaisesRegex(ValueError, "schema"):
            arrow.encode_ipc(changed)

    def test_inprocess_buffer_ownership_survives_source_del(self):
        # Tests Arrow's documented lifetime-managed zero-copy buffer reference.
        # This is NOT proof of network or cross-process zero-copy.
        original = bytearray(b"TRINITY-buffer-ownership")
        view = self.pa.py_buffer(original)
        sliced = view.slice(8, 6)
        del original, view
        gc.collect()
        self.assertEqual(sliced.to_pybytes(), b"buffer")

    def test_strict_row_validation_after_arrow_output(self):
        rows = arrow.generate_rows(17)
        table = arrow.table_from_rows(rows)
        self.assertEqual(arrow.validate_rows(arrow.decode_ipc(arrow.encode_ipc(table)).to_pylist()), rows)

    def test_benchmark_json_serializable_no_speed_claim(self):
        result = arrow.benchmark(rows=40, repeats=2, seed=123)
        self.assertEqual(result["rows"], 40)
        self.assertEqual([x["path"] for x in result["results"]], ["json_utf8_records", "arrow_ipc_stream"])
        self.assertTrue(all(x["exact_roundtrip_valid"] for x in result["results"]))
        self.assertTrue(all(x["payload_bytes"] > 0 for x in result["results"]))
        self.assertIn("no network", " ".join(result["limitations"]))
        json.dumps(result, allow_nan=False)

    def test_cli_benchmark_and_output(self):
        p = subprocess.run([sys.executable, "-m", "trinitylab.data", "arrow-benchmark", "--rows", "15", "--repeats", "2"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        parsed = json.loads(p.stdout)
        self.assertTrue(all(x["exact_roundtrip_valid"] for x in parsed["results"]))


if __name__ == "__main__":
    unittest.main()
