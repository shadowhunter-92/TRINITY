"""Measurable interchange paths with clear network/in-process distinctions.

The memoryview path is zero-copy *within one process*, not cross-network serialization.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import struct
import sys
import time
import tracemalloc
from array import array

from trinitylab.util import median_ms, metadata

MAGIC = b"TRD1"  # laboratory-only format; do not use in production
MAX_VALUES = 1_000_000


def make_values(count: int, seed: int = 19) -> array:
    if not 1 <= count <= MAX_VALUES:
        raise ValueError(f"Number of values must be between 1 and {MAX_VALUES}")
    rng = random.Random(seed)
    return array("d", [rng.uniform(-500, 500) for _ in range(count)])


def encode_json(values: array) -> bytes:
    return json.dumps(values.tolist(), separators=(",", ":"), allow_nan=False).encode("utf-8")


def decode_json(payload: bytes) -> list[float]:
    if len(payload) > MAX_VALUES * 40:
        raise ValueError("JSON payload too large")
    obj = json.loads(payload)
    if not isinstance(obj, list) or not 1 <= len(obj) <= MAX_VALUES:
        raise ValueError("Expected bounded JSON array")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in obj):
        raise ValueError("Only finite numeric values supported")
    return [float(v) for v in obj]


def encode_binary(values: array) -> bytes:
    if len(values) > MAX_VALUES:
        raise ValueError("Too many values")
    if any(not math.isfinite(v) for v in values):
        raise ValueError("Only finite numeric values supported")
    return MAGIC + struct.pack("<I", len(values)) + struct.pack("<" + "d" * len(values), *values)


def decode_binary(payload: bytes) -> list[float]:
    if len(payload) < 8 or payload[:4] != MAGIC:
        raise ValueError("Invalid binary header")
    count = struct.unpack_from("<I", payload, 4)[0]
    if not 1 <= count <= MAX_VALUES or len(payload) != 8 + 8 * count:
        raise ValueError("Invalid binary payload length")
    numbers = list(struct.unpack_from("<" + "d" * count, payload, 8))
    if any(not math.isfinite(v) for v in numbers):
        raise ValueError("Binary payload contains nonfinite value")
    return numbers


def share_memoryview(values: array) -> memoryview:
    """Borrow storage; caller must keep source alive, must not resize it."""
    if values.typecode != "d":
        raise ValueError("Expected array('d')")
    return memoryview(values).toreadonly()


def _measure_once(encode, decode) -> dict:
    tracemalloc.start()
    try:
        start = time.perf_counter()
        payload = encode()
        encoded = time.perf_counter()
        values = decode(payload)
        result = math.fsum(values)
        done = time.perf_counter()
        peak = tracemalloc.get_traced_memory()[1]
        return {"encode_s": encoded - start, "decode_and_sum_s": done - encoded, "total_s": done - start, "peak_traced_bytes": peak, "checksum": result, "payload_size": payload.nbytes if isinstance(payload, memoryview) else len(payload), "zero_copy_borrowed": isinstance(payload, memoryview)}
    finally:
        tracemalloc.stop()


def benchmark(rows: int = 3000, repeats: int = 7, seed: int = 19) -> dict:
    if not 1 <= repeats <= 1000:
        raise ValueError("repeats must be 1..1000")
    source = make_values(rows, seed)
    expected = math.fsum(source)
    candidates = [
        ("json_utf8", "serialized_bytes", lambda: encode_json(source), decode_json),
        ("binary_struct_le", "serialized_bytes", lambda: encode_binary(source), decode_binary),
        ("shared_memoryview", "same_process_borrowed_buffer", lambda: share_memoryview(source), lambda x: x),
    ]
    results = []
    for name, scope, encoder, decoder in candidates:
        observations = [_measure_once(encoder, decoder) for _ in range(repeats)]
        if any(not math.isclose(obs["checksum"], expected, rel_tol=1e-11, abs_tol=1e-8) for obs in observations):
            raise AssertionError(f"Data integrity failed for {name}")
        results.append({
            "path": name,
            "scope": scope,
            "median_encode_ms": median_ms([o["encode_s"] for o in observations]),
            "median_decode_and_sum_ms": median_ms([o["decode_and_sum_s"] for o in observations]),
            "median_end_to_end_ms": median_ms([o["total_s"] for o in observations]),
            "median_peak_traced_python_bytes": int(statistics.median(o["peak_traced_bytes"] for o in observations)),
            "payload_or_view_bytes": observations[0]["payload_size"],
            "checksum_valid": True,
        })
    return {"project": "trinity_data", "scenario": "same_process_float64_vector", "rows": rows, "seed": seed, "repeats": repeats, "results": results, "environment": metadata(), "notes": [
        "memoryview is borrowed memory in one process, not a wire format or network zero-copy protocol",
        "JSON/struct produce bytes; in-memory view avoids serialization and is not an apples-to-apples transport alternative",
        "tracemalloc sees primarily Python allocations, not all native RSS or system buffers",
        "Python timing and allocation instrumentation add overhead; benchmark relative paths on the same host",
        "Binary little-endian format is custom demo, not an industry standard; prefer Apache Arrow for interoperable columnar formats",
    ]}
