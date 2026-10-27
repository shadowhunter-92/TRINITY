# Executed verification results

These results were **actually executed** on the attached build environment. They are not independently verified production measurements.

- Python version: `3.13.5`
- Test suite: **38 tests passed**, including local-only network tests and two integration tests.
- Benchmark runner: **3/3** workstreams succeeded.
- End-to-end simulated Industrial → Data → Compute pipeline: **passed**.
- Disposable loopback Modbus read test: **passed**.

## Representative measured medians

| Workstream / configuration | Measured median | Conditions |
| --- | ---: | --- |
| Compute — reference Python | 0.2452 ms | Synthetic MLP, batch 6, no model loading |
| Compute — batched Python | 0.2674 ms | Same floating-point contract and inputs |
| Industrial — mapping snapshot | 0.0013 ms | 3 simulated signals, no PLC/network |
| Data — JSON UTF-8 | 8.9938 ms | 2,000 doubles, encode+decode+checksum |
| Data — demo little-endian binary | 3.2727 ms | Same local workload |
| Data — same-process memoryview | 0.1897 ms | Borrowed data, NOT a transport alternative |

Optional CPU NumPy backend: **True** numerical parity check; measured 0.0255 ms median for its separate default-input experiment. This is a different workload than the `bench_all.py` compute run and must not be placed into that run's speedup comparison.

## Correct interpretation

* The binary codec is a tiny laboratory format, not a proposed replacement for Arrow or Protocol Buffers.
* The memoryview path is not cross-process, cross-machine, network or universal zero-copy.
* The industrial snapshot timing is not an industrial gateway throughput measurement.
* The Compute model is an 8-output toy network, not a general LLM inference result.
* No monetary savings, commercial demand, hardware portability or trillion-dollar valuation has been established.

For full host metadata, raw measurements, caveats and parameters inspect `benchmarks/baselines/lab_benchmarks.json`, `benchmarks/baselines/compute_numpy_optional.json`, and `docs/BENCHMARKS.md`.
