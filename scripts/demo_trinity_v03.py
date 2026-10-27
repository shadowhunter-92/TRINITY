#!/usr/bin/env python3
"""Opt-in local OPC UA -> validated Arrow IPC -> ONNX Runtime CPU demonstration.

Not diagnostic; does not access physical industrial equipment. No external URLs.
"""
from __future__ import annotations

import asyncio
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trinitylab.compute.core import ReferenceEngine, compare_outputs, make_model
from trinitylab.compute.onnx_adapter import ONNXRuntimeCPUEngine
from trinitylab.data.arrow_adapter import (assert_identical, decode_ipc, encode_ipc,
                                           table_from_rows, validate_rows)
from trinitylab.industrial.opcua import load_opcua_profile
from scripts.demo_opcua_loopback import ephemeral_loopback_port


def validate_snapshot(snapshot: dict, expected_ids: tuple[str, ...]) -> tuple[list[dict], list[float]]:
    """Refuse incomplete, bad-quality, malformed, or non-finite telemetry."""
    if snapshot.get("source") != "opcua_explicit_local_read":
        raise ValueError("unexpected telemetry origin")
    signals = snapshot.get("signals")
    if not isinstance(signals, list) or tuple(s.get("signal_id") for s in signals) != expected_ids:
        raise ValueError("signal ordering or identities differ from approved model")
    values = []
    rows = []
    for signal in signals:
        value = signal.get("value")
        if signal.get("quality") != "good" or type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError("only finite good-quality measurements permitted")
        values.append(float(value))
        stamp = signal.get("source_timestamp")
        if not isinstance(stamp, str):
            raise ValueError("source timestamp missing")
        dt = datetime.fromisoformat(stamp)
        if dt.tzinfo is None:
            raise ValueError("source timestamp must include timezone")
        rows.append({"sensor_id": signal["signal_id"],
                     "time_ms": int(dt.timestamp() * 1000), "reading": float(value)})
    return validate_rows(rows), values


async def run_demo() -> dict:
    # Importing asyncua and opening a local server happen only on explicit invocation.
    from asyncua import Server, ua
    from trinitylab.industrial.opcua import read_opcua_snapshot

    profile = load_opcua_profile(ROOT / "fixtures/industrial/opcua_profile_v1.json")
    endpoint = f"opc.tcp://127.0.0.1:{ephemeral_loopback_port()}/trinity/integration/"
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("TRINITY v0.3 disposable local test server")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    ns = await server.register_namespace(profile.namespace_uri)
    equipment = await server.nodes.objects.add_object(ns, "SyntheticPump")
    example = {"MotorTemperature": 42.0, "ShaftSpeed": 1800.0, "LinePressure": 1234.0}
    for identifier, raw in example.items():
        await equipment.add_variable(ua.NodeId(identifier, ns), identifier, raw)
    async with server:
        snapshot = await read_opcua_snapshot(profile, endpoint, enable_network=True)
    expected_ids = tuple(s.signal_id for s in profile.signals)
    rows, original = validate_snapshot(snapshot, expected_ids)
    table = table_from_rows(rows)
    encoded = encode_ipc(table)
    restored = decode_ipc(encoded).to_pylist()
    assert_identical(restored, rows)
    recovered = [float(row["reading"]) for row in restored]
    if recovered != original:
        raise AssertionError("the Arrow IPC boundary changed sensor measurements")

    model = make_model(len(recovered), 6, 2, seed=29)
    inference_batch = [[v / 1000.0 for v in recovered]]
    reference = ReferenceEngine(model).infer(inference_batch)
    cpu = ONNXRuntimeCPUEngine(model)
    actual = cpu.infer(inference_batch)
    correctness = compare_outputs(reference, actual, atol=cpu.atol, rtol=cpu.rtol)
    if not correctness["passed"]:
        raise AssertionError("ONNX output deviates from Python reference")
    return {
        "project": "trinity_integration_v03", "synthetic_only": True,
        "pipeline": ["opcua_loopback_read_only", "industrial_good_quality_gate", "arrow_ipc_stream", "onnxruntime_cpu"],
        "machine_id": profile.machine_id, "profile_version": profile.version,
        "input_signal_ids": list(expected_ids), "validated_sensor_values": recovered,
        "arrow_payload_bytes": encoded.size, "arrow_roundtrip_valid": True,
        "reference_output": reference[0], "onnx_output": actual[0],
        "compute_correctness": correctness, "runtime_versions": cpu.versions,
        "notice": "Synthetic laboratory inputs and meaningless toy neural output; no industrial prediction, field access, control, performance, or cost-saving claim",
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_demo()), indent=2, allow_nan=False))
