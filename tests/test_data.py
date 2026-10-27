import math
import unittest
from array import array
from pathlib import Path

from trinitylab.data.core import (benchmark, decode_binary, decode_json, encode_binary,
                                  encode_json, make_values, share_memoryview)
from trinitylab.data.schema import compare_schemas, load_schema, parse_schema

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "data"


class DataTests(unittest.TestCase):
    def test_repeatable_workload(self):
        self.assertEqual(make_values(10, 9), make_values(10, 9))

    def test_json_roundtrip(self):
        source = make_values(20)
        self.assertEqual(decode_json(encode_json(source)), list(source))

    def test_binary_roundtrip_and_endianness(self):
        source = array("d", [1.0, -2.5, 1024.0])
        payload = encode_binary(source)
        self.assertEqual(payload[:4], b"TRD1")
        self.assertEqual(decode_binary(payload), list(source))

    def test_invalid_binary_payload(self):
        for malformed in [b"", b"TRD1", b"TRD1\xff\xff\xff\xff", encode_binary(array("d", [1.0]))[:-1]]:
            with self.subTest(payload=malformed):
                with self.assertRaises(ValueError):
                    decode_binary(malformed)

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            encode_binary(array("d", [math.nan]))
        with self.assertRaises(ValueError):
            decode_json(b"[NaN]")
        with self.assertRaises(ValueError):
            decode_json(b'[true]')

    def test_memoryview_is_borrowed_and_read_only(self):
        vals = make_values(4)
        view = share_memoryview(vals)
        self.assertIs(view.obj, vals)
        self.assertTrue(view.readonly)
        with self.assertRaises(TypeError):
            view[0] = 2.0

    def test_benchmark_validates_checksums(self):
        r = benchmark(rows=32, repeats=3)
        self.assertEqual(len(r["results"]), 3)
        self.assertTrue(all(x["checksum_valid"] for x in r["results"]))
        self.assertIn("same_process_borrowed_buffer", [x["scope"] for x in r["results"]])

    def test_compatible_schema(self):
        a = load_schema(ROOT / "schema_v1.json")
        b = load_schema(ROOT / "schema_v2_compatible.json")
        r = compare_schemas(a, b)
        self.assertTrue(r["compatible"])
        self.assertIn("confidence", r["added"])

    def test_breaking_schema(self):
        a = load_schema(ROOT / "schema_v1.json")
        b = load_schema(ROOT / "schema_v2_breaking.json")
        r = compare_schemas(a, b)
        self.assertFalse(r["compatible"])
        self.assertGreaterEqual(len(r["issues"]), 2)

    def test_reject_duplicate_schema_field(self):
        with self.assertRaises(ValueError):
            parse_schema({"fields": [{"name": "x", "type": "int32", "nullable": False}, {"name": "x", "type": "int64", "nullable": False}]})
