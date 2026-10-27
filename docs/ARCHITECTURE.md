# TRINITY v0.1 — Architecture and engineering contracts

## Intent

Each experiment is independent. No central infrastructure platform, cloud connection, model registry, device crawler, data collection agent, or background daemon is installed or started. That decision makes tests reproducible and minimizes accidental access to real hardware or private data.

## Compute

```text
seeded random weights + seeded input batch
          |
      TinyMLP contract
          |
    +-----+------+-----------------+
    |            |                 |
Python reference  Python batched   NumPy matrix multiply [optional]
    |            |                 |
    +------------+-----------------+
                 |
    shape/finite/numerical parity gate
                 |
      median/p95, JSON report
```

- Shape contract: input `N×D`, hidden `N×H`, output `N×O`.
- Math: `ReLU(XW1 + b1) W2 + b2`.
- Each backend returns lists of finite Python floats, compared elementwise with explicitly chosen tolerances.
- To avoid an accidental environmental dependency, the default Python modes do not import NumPy.
- The vectorized backend preloads weights, but input conversion/output conversion are measured as part of each inference request; this is intentionally conservative.
- It is a mathematical contract verification harness, **not** a full model compiler. Next genuine model portability milestone: well-defined ONNX subset and supported real runtimes.

## Industrial

```text
profile_v1.json + fixture registers.json
                   |
     parse / validate / bounds-check
                   |
            snapshot quality
                   |
              JSON report

profile_v1.json + profile_v2.json
                   |
           field-by-field drift
                   |
              JSON report

optional authorized Modbus TCP endpoint
                   |
    OFF by default; local-only default
                   |
    FC03 or FC04; <=125 registers
                   |
      header + length validation
                   |
          JSON diagnostic report
```

- A profile explicitly binds a stable `signal_id` to a Modbus zero-based address, unit, scale, offset and plausible minimum/maximum.
- Quality is `good`, `missing`, or `out_of_range`. **This does not validate a signal's physical meaning.**
- Drift compares two versions of an explicitly maintained mapping; **it does not autonomously infer changes in a running machine**.
- The Modbus implementation is deliberately tiny and does not offer dynamic function-code selection beyond two read functions.
- The Modbus client connects to a single resolved numeric address, uses a finite timeout, validates transaction/unit/function/length/quantity, and never sends a write request.
- The benchmark times in-memory snapshot generation only; it does not benchmark device/network throughput.

## Data

```text
seeded array('d') source
         |
   +-----+------------+------------------+
   |                  |                  |
  JSON UTF-8       demo LE binary    read-only memoryview
   |                  |                  |
 decode to floats  decode to floats  borrow same backing array
   +------------------+------------------+
                      |
               math.fsum parity
                      |
        timings + traced Python allocations

schema_v1.json + schema_v2.json -> parse -> compatibility issues
```

- Binary payload is `b'TRD1' + little-endian uint32 length + little-endian float64 values`.
- All payloads require finite values and bounded lengths; bogus headers, truncation and extra bytes are rejected.
- A memoryview references the original array's memory. It does **not** cross a process or a network and is read-only only through that view (the owner can still mutate).
- Schema compatibility means the *new schema can accept values from the old schema*, subject to explicitly defined type-widening and nullability rules; no semantic guarantees.
- The profiler uses `time.perf_counter()` and `tracemalloc`; its reported allocation peaks cover Python-traced allocations rather than true process-wide memory.

## Shared contracts

- Python 3.10+; standard library for default code paths.
- JSON reports are stable in shape and source order, but timing values cannot be deterministic.
- `--output` is an explicit local path, never an upload destination.
- CI gate: `python scripts/verify_all.py`.
- No encryption/authentication, multi-tenant controls, cloud deployment or service-level claims.

## Deliberately excluded

Hardware reverse engineering, bypassing proprietary protections, PLC writes, safety-loop control, hidden data collection, arbitrary serialization of Python objects, unsafe pickle formats, unauthorized network discovery, and automatic use of remote systems.
