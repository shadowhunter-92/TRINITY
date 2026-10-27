# Benchmark method, repeatability, and interpretation

## Reproduce the numbers

```bash
python scripts/verify_all.py
```

The test suite checks correctness, safety gates and expected failure cases first; `bench_all.py` then performs three experiments and writes `results/lab_benchmarks.json`.

The benchmark runner pins `PYTHONHASHSEED=0` and asks common BLAS backends to use one thread. Model weights and data values are generated from fixed seeds. This **does not fix CPU frequency, OS scheduling, NumPy/BLAS versions or workload contention**; elapsed time is not bit-for-bit reproducible.

## Defined lab workloads

| Project | Benchmark input | Metric | Not measured |
| --- | --- | --- | --- |
| Compute | Two-layer float64 MLP: input 24, hidden 32, output 8, batch 6 | Median and p95 latency of each execution path (12 iterations, three warmups) | GPU, network, real LLM, electricity, production cost |
| Industrial | Three mapped fixture signals, 250 simulated snapshots | Median local snapshot processing time | PLC/SCADA/network latency, security, operational safety |
| Data | 2,000 float64 values, five repetitions/path | Encode, decode+consume, total, output bytes and traced Python allocation peak | Network zero-copy, Arrow, total native RSS, database workloads |

The in-process memoryview path is an **illustrative upper-bound type of result** for a shared-memory use case and is not directly comparable to serialized wire formats. All paths verify numerical equivalence.

## Interpret performance carefully

- A change in operation semantics, output accuracy or payload ownership can make a faster test invalid.
- JSON and binary serialization create durable bytes; a view of owned memory has a different contract.
- Tracemalloc instrumentation itself adds overhead and misses many native memory allocations.
- Speedups are not indicative of money saved until measured as part of complete customer workflows including procurement, device costs, integration, cloud bills and operations.
- Before publishing any marketing results, include test machine, OS, Python/NumPy version, thread settings, dataset, confidence intervals, benchmark source and the actual target workload.

The tracked JSON example in `benchmarks/baselines/lab_benchmarks.json` is an initial environment-specific record, not a third-party reproducibility claim.

## Required next benchmark improvements

- Compute: realistic model import, runtime version pinning, accuracy fixtures, latency distribution, throughput under load and cost per verified inference.
- Industrial: realistic equipment profiles, authorized protocol simulators, error injection, reconnection, time synchronization, mapping drift detection accuracy and gateway soak tests.
- Data: actual Arrow IPC/Flight, schemas with nulls and nested data, buffer-lifetime correctness, end-to-end network transfers and realistic database/AI application pipelines.
