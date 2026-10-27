# Codex handoff — next engineering work

## Working agreement

Before each Codex task, read `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`,
`docs/ROADMAP.md`, `docs/SECURITY.md` and this page. Work in a feature branch,
not directly on `main`. Run the full verification suite and report actual output.
Do not claim real-world portability or savings from synthetic benchmarks.

## Task A — Compute ONNX adapter (suggested first PR)

**Goal:** Add an optional, opt-in ONNX Runtime CPU provider adapter capable of loading
one small licensed ONNX test model, without changing the standard-library offline core.

**Done means:**
- Explicit optional dependency, version information and clearly licensed model artifact or generation script.
- Shape/type validation, pinned deterministic inputs and reference outputs; configurable tolerance.
- Numeric parity and error-path tests; skip gracefully if the dependency is unavailable.
- Reproducible latency distributions; compare like-for-like input/output conversion.
- No unverified GPU/CUDA/ROCm claims or auto-downloaded model weights.

## Task B — Industrial OPC UA simulator (suggested second PR)

**Goal:** Add a standards-based, opt-in, read-only OPC UA connector against a local test
server, preserving network-disabled default and keeping Modbus code read-only.

**Done means:**
- Loopback-only simulator fixture; no real PLC endpoint or discovery.
- Explicit address-space mapping, sample timestamps, value quality and missing-data cases.
- Tests for reconnect, timeouts, malformed node metadata and profile drift.
- Security notes explaining where real authentication, encryption and OT review are still required.
- No writes to PLCs, no scanning and no claims of safety certification.

## Task C — Data Arrow comparison (implemented in separate PR)

**Goal:** Add opt-in Apache Arrow baseline for one typed dataset and make fair comparisons
against laboratory JSON/binary codecs without equating borrowed views to network transfer.

**Done means:**
- Explicit nullable schema and metadata; missing values and NaN handling specified.
- In-process Arrow table and IPC encode/decode experiments, with identical verified outputs.
- Memory ownership/lifetime checks and tests for incompatible schema versions.
- Per-stage CPU/latency/memory metrics and transparent limitations.
- No claim that the benchmark proves cross-machine zero-copy or global cloud savings.

## Integration milestone

Extend the entirely synthetic Industrial → Data → Compute demonstration only after all
three adapters exist, with explicit contracts and deterministic validation fixtures.

## Suggested Codex opening prompt

> Read AGENTS.md and docs/CODEX_HANDOFF.md. Implement Task A on a feature branch in
> small commits, preserving offline-by-default behavior. Add tests and documentation.
> Execute the repository verification commands, record observed outcomes and known
> limitations, and prepare a PR summary. Do not broaden scope or touch live systems.

### Data v0.2 handoff

The optional Arrow IPC stream adapter lives in `trinitylab/data/arrow_adapter.py` and is documented in [`ARROW_ADAPTER.md`](ARROW_ADAPTER.md). Run the new dedicated CI job prior to merging; no PyArrow requirement may leak into core offline paths. Future development should focus on realistic typed workloads, process-native peak-memory measurement, and batch-size investigations—not an unsupported global performance claim.
