# TRINITY v0.3: optional three-runtime integration

This laboratory demonstration runs a disposable **loopback-only, read-only OPC UA** server, validates typed and bounded values using the approved v1 pump profile, serializes the validated records using an **Apache Arrow IPC stream**, round-trips all readings with exact equality, and executes a locally constructed two-layer MLP using **ONNX Runtime CPU**. It compares the float32 ONNX output to a float64 Python reference within documented tolerances. It does **not** communicate with or control a real device.

```bash
python -m pip install -e '.[integration-v03]'
python scripts/demo_trinity_v03.py
python -m unittest discover -s tests -v
```

All external runtimes are **optional**; the regular standard-library-only suite still runs without them. The demo uses `127.0.0.1` only and explicitly starts a disposable local server; no remote IP, credentials, machine discovery, or PLC writes are permitted. A local server uses OPC UA NoSecurity because all traffic is confined to loopback. This configuration is **not** appropriate for production industrial environments.

The experiment validates expected signal IDs and ordering, good quality, finite numeric values, timezone-aware timestamps and round-trip bit-preserving Python float64 values. Any non-good telemetry causes failure before inference. It does **not** check industrial causal semantics, calibration, real sensor provenance, clock synchronization, model fitness, optimization savings, or operational safety.

The report contains project name, ordered pipeline, schema-verified Arrow IPC payload size, exact records, an ONNX vs Python parity result, dependency versions and a clear non-diagnostic notice. Times and byte counts are not promises of reduced latency or cost. For realistic evaluation, use independent non-production workloads and do not promote this code to plant networks.

## Merge notes

This branch intentionally consolidates the previously separate Compute ONNX, Industrial OPC UA and Data Arrow development lines in addition to the new integration. The original PRs #5 and #6 were independently green before PR #4 merged, but conflicts in shared docs and CI now prevent their direct merging. The consolidated PR must pass all offline and all three optional runtime jobs, plus the new integration job. Only then should the superseded PRs be closed and the integration merged through branch protection.
