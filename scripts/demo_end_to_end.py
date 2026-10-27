#!/usr/bin/env python3
"""Offline proof of composition: synthetic plant -> demo codec -> toy AI.

No real machinery, AI deployment, network access or production control involved.
"""
from __future__ import annotations

import math
import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trinitylab.compute.core import ReferenceEngine, BatchedEngine, compare_outputs, make_model
from trinitylab.data.core import decode_binary, encode_binary
from trinitylab.industrial.core import load_profile, load_registers, snapshot
from trinitylab.util import emit


def build_report() -> dict:
    fixture = ROOT / "fixtures" / "industrial"
    snap = snapshot(load_profile(fixture / "profile_v1.json"), load_registers(fixture / "registers.json"))
    if any(s["quality"] != "good" for s in snap["signals"]):
        raise ValueError("Cannot perform toy inference with missing or invalid signals")
    reading_values = array("d", [s["value"] for s in snap["signals"]])
    payload = encode_binary(reading_values)
    recovered = decode_binary(payload)
    if recovered != list(reading_values):
        raise AssertionError("Data transfer failed integrity check")
    toy_inputs = [[value / 1000 for value in recovered]]
    model = make_model(len(toy_inputs[0]), 6, 2, seed=29)
    reference = ReferenceEngine(model).infer(toy_inputs)
    alternative = BatchedEngine(model).infer(toy_inputs)
    correctness = compare_outputs(reference, alternative)
    if not correctness["passed"]:
        raise AssertionError("Compute paths disagree")
    return {
        "project": "trinity_lab_integration", "source": "offline_industrial_fixture", "data_codec": "demo_little_endian_binary_not_standardized", "serialized_bytes": len(payload),
        "signal_quality": [s["quality"] for s in snap["signals"]], "input_signal_ids": [s["signal_id"] for s in snap["signals"]],
        "verified_sensor_values": recovered, "toy_neural_network_output": reference[0], "runtime_comparison": correctness,
        "notice": "Toy mathematical output, not a fault score, production prediction, real AI deployment, or machinery diagnostic"
    }


if __name__ == "__main__":
    emit(build_report())
