# Industrial v0.2 — optional, read-only OPC UA laboratory adapter

This is an **experimental local-only connector**, not an industrial gateway or safety-certified product. It is designed to validate a versioned, explicitly configured signal map against a disposable `asyncua` server. In production, OPC UA generally needs a deliberate certificate trust model, authenticated users, encrypted channels, firewall/segmentation review, asset-owner authorization and operational safety assessment. None of those controls is implemented here.

## Installation and execution

Python 3.10+ is required. Core simulations and tests do not depend on any third-party packages.

```bash
python scripts/verify_all.py
python -m pip install '.[industrial-opcua]'
python scripts/demo_opcua_loopback.py
python -m unittest discover -s tests -p 'test_opcua.py' -v
```

The integration demo creates a disposable OPC UA server on an ephemeral port bound to `127.0.0.1`, registers a namespace, creates **non-writable** variables, obtains two snapshots through distinct client sessions, validates engineering units and evaluates mapping drift. No real PLC or remote endpoint is accessed.

## Explicit contract

The input profile is JSON (`fixtures/industrial/opcua_profile_v1.json`) containing:

- `machine_id` (bounded safe identifier), `version` (strictly increasing integer) and `namespace_uri` (restricted `urn:` URI).
- `signals[]` each with unique `signal_id` and unique string `identifier`. Numeric namespace indexes are resolved from `namespace_uri` on each connection, rather than baked into the profile.
- Per-signal `unit`, `scale`, `offset`, `minimum` and `maximum` with bounded finite numeric values.

The client retrieves each requested node's OPC UA **DataValue**. If the status is Good and its content is a finite non-boolean integer/float, the engineering-unit conversion is applied. Quality is `good`, `out_of_range`, `invalid_type`, `bad_status`, `timeout`, or `read_error`; timestamps are represented in UTC where present. A missing node is recorded as `read_error`. No values are substituted or inferred. `captured_at` describes the client's collection time, not the sensor's measurement time. Source timestamps from the server are separately preserved when available.

## Deliberate safety boundaries

1. Calls without `enable_network=True` fail **before** importing `asyncua`.
2. Only literal `opc.tcp://127.0.0.1:<port>/...` URLs are permitted. DNS names, credentials, remote addresses, query parameters and redirects are not supported. No auto-discovery or scanning.
3. No `write_value`, `call_method`, browsing or subscriptions are implemented in TRINITY's client. Session-handshake service operations are still performed by the OPC UA library.
4. Bounded timeouts, bounded profile sizes (128 nodes maximum) and **no automatic retries**. Separate snapshots instantiate separate sessions.
5. The demo uses unencrypted OPC UA **only on loopback**. Never expose it outside the local test host or repurpose the adapter to operate real equipment.
6. No claim of production fault tolerance, secured OT deployment, interoperability certification, or operational/safety suitability.

## Evidence and testing

Unit tests run without the optional dependency and cover profile parsing, profile drift, disabled network, remote endpoint rejection, scalar validation, bad quality, numerical bounds, and timestamps. Optional tests exercise a real loopback server, reconnect through a fresh session, and an unavailable endpoint. `CI` installs `asyncua` only in its dedicated OPC UA job to ensure real protocol execution is exercised on GitHub rather than silently skipped.

## Known limitations

- Supports scalar float/integer measurements and string NodeIds in one namespace; no arrays, ExtensionObjects, event subscriptions, writes, browse discovery, service resilience or certificate handling.
- Not suitable for remote, authenticated, or encrypted production integration.
- Timing measurements in the general industrial benchmark are *in-memory* only; the demo does not report industrial-network performance.
- Per-node failures are quality annotations; session-wide failures raise `OPCUAError` with a bounded generic message.

Reference: [FreeOpcUa opcua-asyncio](https://github.com/FreeOpcUa/opcua-asyncio) (the optional library used for transport).
