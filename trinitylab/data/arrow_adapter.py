"""Optional, bounded Apache Arrow streaming IPC experiment.

All data is synthetic, trusted and generated in this process. No network endpoints,
external files, or cross-host zero-copy functionality are implemented.

Both benchmark candidates consume identical *typed* rows. Timed stages include
materialization into a format-specific representation (Arrow Table or Python
objects), encoding, decoding, and checking the complete reconstructed output.
The initial input row generation, which is common to both candidates, is excluded.
"""
from __future__ import annotations

import importlib
import json
import math
import random
import statistics
import time
import tracemalloc
from typing import Any

from trinitylab.data.schema import compare_schemas, parse_schema
from trinitylab.util import median_ms, metadata, percentile_ms

MAX_ROWS = 100_000
MAX_IPC_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024 * 1024
DATASET = "trinity.synthetic.sensor_readings.v1"
SCHEMA_METADATA = {b"trinity.dataset": DATASET.encode("ascii"), b"trinity.schema_version": b"1"}
# A precisely typed, explicitly nullable record. Strict schema matching is a
# correctness property for IPC. Separate schema evolution checks are structural.
SENSOR_SCHEMA = parse_schema({"fields": [
    {"name": "sensor_id", "type": "string", "nullable": False},
    {"name": "time_ms", "type": "int64", "nullable": False},
    {"name": "reading", "type": "float64", "nullable": True},
]})


def require_arrow():
    """Import only when the feature is explicitly selected; clear error if absent."""
    try:
        return importlib.import_module("pyarrow")
    except ImportError as exc:
        raise RuntimeError('Apache Arrow is optional: install with python -m pip install -e ".[data-arrow]"') from exc


def generate_rows(count: int = 1000, seed: int = 19) -> list[dict[str, Any]]:
    if type(count) is not int or not 1 <= count <= MAX_ROWS:
        raise ValueError(f"rows must be in 1..{MAX_ROWS}")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    return [
        {"sensor_id": f"sensor_{i % 23:02d}",
         "time_ms": 1_700_000_000_000 + i * 1000,
         "reading": None if i % 11 == 0 else round(rng.uniform(-200, 200), 5)}
        for i in range(count)
    ]


def validate_rows(rows: object) -> list[dict[str, Any]]:
    """Validate exact shape and primitives, before conversion or acceptance."""
    if type(rows) is not list or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("expected a bounded, nonempty row list")
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != set(SENSOR_SCHEMA):
            raise ValueError(f"unexpected columns at row {index}")
        name, timestamp, value = row["sensor_id"], row["time_ms"], row["reading"]
        if type(name) is not str or not 1 <= len(name) <= 80 or "\x00" in name:
            raise ValueError(f"invalid sensor_id at row {index}")
        if type(timestamp) is not int or not -(2**63) <= timestamp < 2**63:
            raise ValueError(f"invalid time_ms at row {index}")
        if value is not None and (type(value) is not float or not math.isfinite(value)):
            raise ValueError(f"invalid reading at row {index}")
    return rows


def arrow_schema(pa=None):
    pa = pa or require_arrow()
    return pa.schema([
        pa.field("sensor_id", pa.string(), nullable=False),
        pa.field("time_ms", pa.int64(), nullable=False),
        pa.field("reading", pa.float64(), nullable=True),
    ], metadata=SCHEMA_METADATA)


def table_from_rows(rows: list[dict[str, Any]], pa=None):
    pa = pa or require_arrow()
    validate_rows(rows)
    schema = arrow_schema(pa)
    columns = [[row[name] for row in rows] for name in SENSOR_SCHEMA]
    return pa.Table.from_arrays([
        pa.array(values, type=field.type, from_pandas=False)
        for field, values in zip(schema, columns)
    ], schema=schema)


def encode_ipc(table, pa=None):
    pa = pa or require_arrow()
    if not table.schema.equals(arrow_schema(pa), check_metadata=True):
        raise ValueError("unexpected Arrow schema or metadata")
    if not 1 <= table.num_rows <= MAX_ROWS:
        raise ValueError("invalid number of Arrow rows")
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    payload = sink.getvalue()  # pyarrow.Buffer, not a Python bytes copy
    if payload.size > MAX_IPC_BYTES:
        raise ValueError("Arrow IPC payload is too large")
    return payload


def decode_ipc(payload, pa=None):
    pa = pa or require_arrow()
    length = payload.size if isinstance(payload, pa.Buffer) else len(payload)
    if not 1 <= length <= MAX_IPC_BYTES:
        raise ValueError("invalid or oversized Arrow IPC payload")
    try:
        with pa.ipc.open_stream(pa.BufferReader(payload)) as reader:
            if not reader.schema.equals(arrow_schema(pa), check_metadata=True):
                raise ValueError("unexpected Arrow IPC schema or metadata")
            table = reader.read_all()
    except (pa.ArrowInvalid, pa.ArrowIOError, EOFError, OSError) as exc:
        raise ValueError("invalid Arrow IPC stream") from exc
    if not 1 <= table.num_rows <= MAX_ROWS:
        raise ValueError("unexpected Arrow IPC row count")
    return table


def json_encode(rows: list[dict[str, Any]]) -> bytes:
    validate_rows(rows)
    payload = json.dumps(rows, allow_nan=False, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_JSON_BYTES:
        raise ValueError("JSON payload too large")
    return payload


def json_decode(payload: bytes) -> list[dict[str, Any]]:
    if not 1 <= len(payload) <= MAX_JSON_BYTES:
        raise ValueError("invalid or oversized JSON payload")
    try:
        rows = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid JSON payload") from exc
    return validate_rows(rows)


def assert_identical(actual, expected: list[dict[str, Any]]):
    """Exact row, null, field-type and value equality (including float64)."""
    if actual != expected:
        raise AssertionError("Arrow/JSON round-trip changed row data, nulls, order or types")


def structural_compatibility(old: dict, new: dict) -> dict:
    """Explicitly separate schema-evolution policy from strict IPC matching."""
    return compare_schemas(old, new)


def _one_run(rows: list[dict[str, Any]], kind: str, pa):
    tracemalloc.start()
    start = time.perf_counter_ns()
    try:
        if kind == "arrow_ipc_stream":
            intermediate = table_from_rows(rows, pa)
            t_build = time.perf_counter_ns()
            payload = encode_ipc(intermediate, pa)
            t_encode = time.perf_counter_ns()
            output = decode_ipc(payload, pa)
            t_decode = time.perf_counter_ns()
            actual = output.to_pylist()
            assert_identical(actual, rows)
            t_valid = time.perf_counter_ns()
            payload_bytes = payload.size
            native_buffers = output.get_total_buffer_size()
        elif kind == "json_utf8_records":
            # Avoid pretending the input Python dicts require no materialization:
            # make a comparable independent row representation for this route.
            intermediate = [row.copy() for row in rows]
            t_build = time.perf_counter_ns()
            payload = json_encode(intermediate)
            t_encode = time.perf_counter_ns()
            actual = json_decode(payload)
            t_decode = time.perf_counter_ns()
            assert_identical(actual, rows)
            t_valid = time.perf_counter_ns()
            payload_bytes = len(payload)
            native_buffers = None
        else:
            raise ValueError("unsupported benchmark path")
        peak_python = tracemalloc.get_traced_memory()[1]
        ns = 1e9
        return {"build_s": (t_build-start)/ns, "encode_s": (t_encode-t_build)/ns,
                "decode_s": (t_decode-t_encode)/ns, "validate_s": (t_valid-t_decode)/ns,
                "total_s": (t_valid-start)/ns, "bytes": payload_bytes,
                "native_buffer_bytes_after_decode": native_buffers,
                "traced_python_peak_bytes": peak_python}
    finally:
        tracemalloc.stop()


def benchmark(rows: int = 1500, repeats: int = 5, seed: int = 19) -> dict:
    if type(repeats) is not int or not 1 <= repeats <= 25:
        raise ValueError("repeats must be in 1..25")
    source = generate_rows(rows, seed)
    pa = require_arrow()
    result = []
    for kind in ("json_utf8_records", "arrow_ipc_stream"):
        _one_run(source, kind, pa)  # equal warmup count; discarded
        observations = [_one_run(source, kind, pa) for _ in range(repeats)]
        stage_keys = ["build_s", "encode_s", "decode_s", "validate_s", "total_s"]
        result.append({
            "path": kind,
            "scope": "same_process_serialize_and_deserialize",
            "median_stages_ms": {name.removesuffix("_s"): median_ms([o[name] for o in observations]) for name in stage_keys},
            "p95_end_to_end_ms": percentile_ms([o["total_s"] for o in observations], 95),
            "payload_bytes": observations[0]["bytes"],
            "peak_traced_python_bytes_median": int(statistics.median(o["traced_python_peak_bytes"] for o in observations)),
            "native_buffer_bytes_after_decode": observations[0]["native_buffer_bytes_after_decode"],
            "exact_roundtrip_valid": True,
        })
    return {"project": "trinity_data", "scenario": "typed_nullable_sensor_rows", "rows": rows,
            "repeats": repeats, "seed": seed, "pyarrow_version": pa.__version__,
            "schema": [{"name": n, **v} for n, v in SENSOR_SCHEMA.items()],
            "schema_metadata": {k.decode(): v.decode() for k, v in SCHEMA_METADATA.items()},
            "results": result, "environment": metadata(), "limitations": [
                "This compares in-process conversion of Python records to JSON bytes versus Arrow IPC buffers; no network, Flight, RDMA, or cross-process benchmarks.",
                "The stages are defined uniformly but Arrow Table construction and JSON dict copying have different work; interpret component timings alongside end-to-end results.",
                "Entire decoded outputs are materialized and verified; times include verification and Python/native integration overhead.",
                "tracemalloc tracks Python allocations only and does not measure native peak RSS; native_buffer_bytes_after_decode is referenced buffers, not memory peak.",
                "Source generation and optional dependency installation are excluded. Timings are host/load dependent; no speedup or monetary savings is implied.",
            ]}
