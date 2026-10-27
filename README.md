# TRINITY — Infrastructure Research Laboratory (v0.1.0)

**Three working, isolated infrastructure experiments in one offline-first Python repository.**

> Research software, not production-certified infrastructure. A successful synthetic benchmark does not establish production performance, portability, security or commercial demand.

| Project | Working laboratory capability | Not implemented yet |
| --- | --- | --- |
| **Compute** | Deterministic 2-layer ReLU MLP, reference and alternate Python CPU runtimes, optional NumPy CPU runtime, numerical correctness, latency/p95 reports | ONNX/model import, CUDA/ROCm, accelerator compilers, production serving |
| **Industrial** | Simulated 16-bit registers, semantic mapping, bounds/quality checks, versioned profile drift, read-only Modbus FC03/FC04 client | OPC UA connector, plant discovery, PLC write, encrypted gateway, production safety certification |
| **Data** | JSON/binary codec tests, borrowed memoryview, data-integrity checks, schema-diff, timing and allocation profiler | Arrow/Flight connector, cross-process zero copy, DB optimization, automatic production tracing |

All three default CLI examples are **local and offline**. Python **3.10+** is required. No third-party library is required to run the tests and main benchmarks. NumPy is optional for an additional accelerated CPU comparison.

## Quick start (Windows / Linux / macOS)

From the repository root:

```bash
python --version
python -m unittest discover -s tests -v
python scripts/bench_all.py
```

Or run both tests and benchmarks in one command:

```bash
python scripts/verify_all.py
```

The file `results/lab_benchmarks.json` is produced by the benchmark runner. Historical example outputs are tracked under `benchmarks/baselines/`; generated `results/` files are intentionally ignored by Git. Times depend on the computer and current machine load; rerun rather than trusting someone else's numbers.

Optional editable install (requires setuptools locally):

```bash
python -m pip install -e .
# Optional: include a third, vectorized CPU backend
python -m pip install -e ".[compute-numpy]"
```

If your Python command is `python3` or `py -3`, substitute accordingly. No installation is needed for `python -m ...` from the repository root.

## 1. Compute: a reproducible neural-network runtime comparison

```bash
python -m trinitylab.compute benchmark --input-dim 32 --hidden-dim 48 --output-dim 8 --batch 8 --seed 7 --warmup 3 --repeats 15
```

Optional NumPy CPU backend:

```bash
python -m trinitylab.compute benchmark --numpy --repeats 15
```

**Pass condition:** Every alternative engine must match the Python reference to `atol=1e-9`, `rtol=1e-7` and produce finite outputs. A failed comparison returns exit code 2. Report includes median and p95 latency, a comparison to reference, parameters, and host metadata. The two Python paths may have different performance; no speedup is presumed.

**What this proves:** a baseline inference-contract and testing harness across CPU implementations for a tiny deterministic neural network. **It does not prove** portability across AI accelerators, real model import, cost savings or compiler performance.

## 2. Industrial: simulated registers and semantic model drift

Signal snapshot:

```bash
python -m trinitylab.industrial snapshot --profile fixtures/industrial/profile_v1.json --registers fixtures/industrial/registers.json
```

Profile change detection:

```bash
python -m trinitylab.industrial drift --old fixtures/industrial/profile_v1.json --new fixtures/industrial/profile_v2.json
```

Local processing benchmark:

```bash
python -m trinitylab.industrial benchmark --profile fixtures/industrial/profile_v1.json --registers fixtures/industrial/registers.json --repeats 1000
```

**Expected fixture:** `motor_temperature` register 100 has raw value 420, scaling 0.1 to 42.0 degC. The profile drift reports the temperature address change, pressure unit and scale change, and newly added flow-rate signal.

The optional Modbus read-only client is **network disabled by default**. To read a **local simulated server** you control:

```bash
python -m trinitylab.industrial modbus-read --host 127.0.0.1 --port 15020 --address 100 --count 3 --enable-network
```

A server must already be running on the given port; without one, connection refusal is expected. Unit tests start an isolated loopback mock server automatically. Remote industrial network access is a separately gated, dangerous option: see [`docs/SECURITY.md`](docs/SECURITY.md). **Never run it against a production PLC without explicit site authorization and OT engineering review.** No write operations exist in the code.

**What this proves:** deterministic mapping, data-quality checks, version drift, and a constrained implementation of Modbus TCP read holding/input registers. **It does not prove:** correct mapping inference, production installation safety, OPC UA compatibility or encrypted industrial access.

## 3. Data: conversion and schema compatibility

```bash
python -m trinitylab.data benchmark --rows 3000 --repeats 7 --seed 19
```

```bash
python -m trinitylab.data schema-diff --old fixtures/data/schema_v1.json --new fixtures/data/schema_v2_compatible.json
```

Breaking example (intentionally returns exit code **1**):

```bash
python -m trinitylab.data schema-diff --old fixtures/data/schema_v1.json --new fixtures/data/schema_v2_breaking.json
```

The benchmark measures three separate routes: UTF-8 JSON bytes, a clearly labeled laboratory little-endian binary format, and a **read-only borrowed `memoryview`** of the same-process `array('d')` source. Reports show median encode/decode-plus-consume/end-to-end times, byte size, traced Python allocation peaks, and verified checksum. The memoryview route is **not** a network-transfer or wire-format alternative, so comparing it to serialization time is illustrative, not a fair claim of end-to-end transport speedup. `tracemalloc` cannot measure all native RSS.

**What this proves:** basic payload correctness, boundary validation, schema evolution rules and a repeatable measurement harness. **It does not prove:** Arrow performance, global cloud savings or interoperable cross-machine zero-copy transport.

## First cross-project integration demonstration

```bash
python scripts/demo_end_to_end.py
```

This executes an **offline** flow: simulated pump readings → checked engineering units → demo binary codec roundtrip → verified toy neural-network inference. Its numerical output has **no predictive or diagnostic meaning**. The goal is to show the three codebases share explicit data contracts.

To test the read-only Modbus code with an automatically started **loopback-only** simulator (no equipment needed):

```bash
python scripts/demo_modbus_loopback.py
```

## Save individual outputs

Each CLI supports `--output results/your_report.json`, for example:

```bash
python -m trinitylab.compute benchmark --output results/compute_run.json
python -m trinitylab.data benchmark --output results/data_run.json
```

`--output` creates parent directories as required. Reports print to standard output as well.

## Repository map

```text
trinity-lab/
├── trinitylab/
│   ├── compute/          # Synthetic MLP + 2 CPU backends + optional NumPy
│   ├── industrial/       # Mapping, drift, local simulator + gated Modbus client
│   ├── data/             # JSON/binary/view codecs + schema checks
│   └── util.py           # Reports, environment metadata and timing helpers
├── tests/                # Offline unittest suite + local mock Modbus server
├── fixtures/             # Deterministic simulation and schema fixtures
├── scripts/
│   ├── bench_all.py      # Produce one repeatable 3-track JSON benchmark report
│   ├── verify_all.py     # Tests + benchmarks; fails on regression
│   ├── demo_end_to_end.py # Industrial -> Data -> Compute, offline
│   └── demo_modbus_loopback.py # Disposable localhost simulator
├── benchmarks/baselines/ # Historical sample outputs (workstation-specific)
├── results/              # Locally generated outputs (ignored by Git)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   ├── BENCHMARKS.md
│   └── ROADMAP.md
├── .github/workflows/ci.yml  # GitHub Actions verification matrix
├── AGENTS.md             # Codex and coding-agent guardrails
├── CONTRIBUTING.md       # Contribution workflow
├── SECURITY.md           # Responsible disclosure entry point
├── pyproject.toml
└── LICENSE
```

## Exit codes

- **0**: success (including schema compatible).
- **1**: intentionally incompatible schema when running `schema-diff`.
- **2**: input/authorization error, inference comparison failure or unexpected validated fault.

## Trillion-dollar infrastructure research direction

The laboratory approach is: establish trustworthy correctness and performance baselines; win a narrowly bounded user problem; acquire real usage and payment evidence; create reliable connectors and open standards; and only then invest in new compilers, industrial semantic layers or network protocols. The trillion-dollar goal is a strategic ambition, not a claim supported by these prototypes.

Read `docs/ROADMAP.md` for next capabilities and go/no-go gates.

## Sources used to guide the laboratory conventions

- Modbus Organization, [Application Protocol Specification V1.1b3](https://www.modbus.org/modbus-specifications) (FC03/FC04 and response framing).
- NumPy, [`numpy.dot` and matrix multiplication documentation](https://numpy.org/doc/stable/reference/generated/numpy.dot.html).
- Apache Arrow, [C Data Interface](https://arrow.apache.org/docs/format/CDataInterface.html) (zero-copy in-process versus cross-process interchange).

This repo uses its own simple test payloads; it does not reproduce third-party implementations of those protocols or formats beyond the documented restricted Modbus read framing.

## Collaborate and continue in Codex

- [Codex instructions](AGENTS.md) and [three concrete next tasks](docs/CODEX_HANDOFF.md)
- [Local development and CI](docs/DEVELOPMENT.md)
- [Contribution guide](CONTRIBUTING.md) and [security reporting](SECURITY.md)
- [GitHub metadata and recommended owner settings](docs/REPOSITORY_SETUP.md)
- [Monorepo design decision](docs/decisions/0001-monorepo.md)

Repository: [shadowhunter-92/TRINITY](https://github.com/shadowhunter-92/TRINITY).

GitHub Actions will run the offline test/benchmark gate across Python 3.10–3.13 on changes to `main` and pull requests. See the CI page for its **actual** status; this documentation does not guarantee remote CI success.

### Industrial v0.2: OPC UA read-only loopback experiment

The optional industrial adapter uses `asyncua` with an **explicitly authorized local test endpoint only**. The default installation remains entirely offline; no PLC is contacted automatically.

```bash
python -m pip install '.[industrial-opcua]'
python scripts/demo_opcua_loopback.py
python -m unittest discover -s tests -p 'test_opcua.py' -v
```

It supports versioned node mappings, engineering-unit scaling, quality flags, timestamps and deterministic drift comparison. **This is not a production OT connector or safety-certified implementation.** See [OPC UA adapter documentation](docs/OPCUA_ADAPTER.md) and [security boundaries](docs/SECURITY.md).
