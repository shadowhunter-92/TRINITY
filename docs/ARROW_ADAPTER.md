# TRINITY Data v0.2 — optional Apache Arrow comparison

## Purpose and supported scope

`trinitylab/data/arrow_adapter.py` is a **laboratory** comparison of Python JSON encoding with Apache Arrow IPC **stream** encoding for *exactly the same generated, typed, nullable records*. It is **not** a network transfer protocol, a replacement for Arrow, or a claim of global cloud savings. It introduces no mandatory third-party dependencies. No downloads or network connections occur at runtime.

## Install and reproduce

```bash
python -m pip install -e '.[data-arrow]'
python -m unittest discover -s tests -v
python -m trinitylab.data arrow-benchmark --rows 2000 --repeats 7 --seed 19 --output results/arrow_benchmark.json
python scripts/verify_all.py
```

Without PyArrow, the core offline tests remain runnable; Arrow integration tests skip and the command exits with an install hint. In GitHub Actions, `Arrow IPC / Python 3.11` installs PyArrow, executes all tests, performs the CLI benchmark, and verifies the JSON report. The core `Python 3.10–3.13 / Ubuntu` matrix stays dependency-free.

## Data contract

Fixture schema matches `fixtures/data/schema_v1.json`:

| Field | Arrow type | Nullable | Semantics |
| --- | --- | --- | --- |
| `sensor_id` | UTF-8 string | no | Simulated sensor name |
| `time_ms` | signed int64 | no | Synthetic millisecond timestamp, not actual telemetry |
| `reading` | IEEE float64 | yes | Synthetic numeric reading; `None` means missing |

The IPC schema also carries required UTF-8 metadata `trinity.dataset=trinity.synthetic.sensor_readings.v1` and `trinity.schema_version=1`. `generate_rows(n, seed)` deterministically inserts a null reading every 11 rows (including row zero). Neither nonfinite readings (`NaN`, ±infinity) nor boolean coercions are accepted. Non-nullable values must be present. The local schema-diff tool allows an additive *nullable* column for a versioned consumer, but the IPC decoder intentionally demands an **exact** schema including metadata; evolution compatibility ≠ same-format interoperability.

## Measurement methodology

For each format, excluding deterministic source generation, the benchmark measures:

1. **Build** — copy row records for JSON, or construct typed native Arrow columns for IPC.
2. **Encode** — serialize compact JSON UTF-8 bytes or Apache Arrow IPC **stream** into an in-memory `pyarrow.Buffer`.
3. **Decode** — parse JSON into Python row dictionaries or IPC into an Arrow `Table`.
4. **Validate** — materialize rows and verify every field, null, timestamp, order, and value against the original.

One warmup for each format is discarded, then 1–25 repetitions are timed. JSON and Arrow both include full round-trip validation. Output includes median stage milliseconds, p95 end-to-end latency, output payload bytes, environment and Arrow version. The result is illustrative only: Arrow Table materialization and shallow JSON record copying are inherently different workloads. Benchmarks should be reproduced on the same host with meaningful application data before making product or business decisions.

`tracemalloc` captures *Python-traced* peaks, **not** native Arrow RSS; referenced Arrow buffer bytes are a **post-decode buffer size**, not total allocated or peak memory. Explicitly distinguish these in analysis. Never directly compare borrowed Python `memoryview` throughput with network transfer efficiency.

## Arrow IPC vs zero-copy

`pa.py_buffer(bytearray(...))` can borrow a Python buffer in the **same process**, maintaining the backing object's lifetime. `pyarrow.Buffer.slice()` can return a non-copying view. Unit tests verify a slice survives deletion of external Python references. The Arrow IPC reader may avoid copies of compatible buffers; **this experiment does not assert that IPC encoding performs zero copies**. There is no cross-process, cross-machine, Flight, RDMA, or shared-memory transport implementation.

## Safety, input bounds, limitations

- `rows` 1–100,000 and `repeats` 1–25; IPC or JSON buffers limited to 64 MiB.
- Do not parse arbitrary untrusted Arrow data; bounding input bytes is not a complete protection against hostile decompression/memory use or native parsing flaws.
- Strict schema and dataset metadata checks before accepting IPC; truncated/corrupt/wrong-version streams are rejected.
- No automated downloading of third-party data, network connections or production datasets.
- The published commands and tests exercise deterministic synthetic data only. No inference about measured business savings follows from a microbenchmark.

## Next experimental gates

Run on representative, permissioned workloads; measure native peak RSS via appropriate process tooling; compare Arrow IPC stream vs Arrow IPC file and suitable memory-mapped readers; test differing batch sizes, nested types, and schema evolution policy; only then consider cross-process transports such as Arrow Flight.

Authoritative protocol API reference: <https://arrow.apache.org/docs/python/ipc.html>.
