"""Tiny deterministic two-layer ReLU network and CPU runtime comparators.

This is a *laboratory* inference example, not an ONNX/TensorRT compiler.
All paths use float64 and must agree within an explicit tolerance.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Protocol

from trinitylab.util import median_ms, metadata, percentile_ms


@dataclass(frozen=True)
class TinyMLP:
    input_dim: int
    hidden_dim: int
    output_dim: int
    w1: tuple[tuple[float, ...], ...]  # [input, hidden]
    b1: tuple[float, ...]
    w2: tuple[tuple[float, ...], ...]  # [hidden, output]
    b2: tuple[float, ...]


def make_model(input_dim: int = 32, hidden_dim: int = 48, output_dim: int = 8, seed: int = 7) -> TinyMLP:
    if not (1 <= input_dim <= 2048 and 1 <= hidden_dim <= 2048 and 1 <= output_dim <= 2048):
        raise ValueError("Model dimensions must be between 1 and 2048")
    rng = random.Random(seed)
    w1 = tuple(tuple(rng.uniform(-0.25, 0.25) for _ in range(hidden_dim)) for _ in range(input_dim))
    b1 = tuple(rng.uniform(-0.1, 0.1) for _ in range(hidden_dim))
    w2 = tuple(tuple(rng.uniform(-0.25, 0.25) for _ in range(output_dim)) for _ in range(hidden_dim))
    b2 = tuple(rng.uniform(-0.1, 0.1) for _ in range(output_dim))
    return TinyMLP(input_dim, hidden_dim, output_dim, w1, b1, w2, b2)


def make_inputs(batch_size: int, input_dim: int, seed: int = 13) -> list[list[float]]:
    if not 1 <= batch_size <= 4096:
        raise ValueError("Batch size must be between 1 and 4096")
    rng = random.Random(seed)
    return [[rng.uniform(-1, 1) for _ in range(input_dim)] for _ in range(batch_size)]


def _check_inputs(model: TinyMLP, batch: list[list[float]]) -> None:
    if not batch or any(len(row) != model.input_dim or any(not math.isfinite(v) for v in row) for row in batch):
        raise ValueError("Inputs must be a nonempty finite batch of correct dimension")


class Engine(Protocol):
    name: str

    def infer(self, batch: list[list[float]]) -> list[list[float]]: ...


class ReferenceEngine:
    name = "python_reference"

    def __init__(self, model: TinyMLP):
        self.model = model

    def infer(self, batch: list[list[float]]) -> list[list[float]]:
        m = self.model
        _check_inputs(m, batch)
        result = []
        for row in batch:
            hidden = []
            for j in range(m.hidden_dim):
                z = m.b1[j]
                for i in range(m.input_dim):
                    z += row[i] * m.w1[i][j]
                hidden.append(max(z, 0.0))
            output = []
            for k in range(m.output_dim):
                z = m.b2[k]
                for j in range(m.hidden_dim):
                    z += hidden[j] * m.w2[j][k]
                output.append(z)
            result.append(output)
        return result


class BatchedEngine:
    """Different loop order; intended for comparison, not promised faster."""
    name = "python_batched"

    def __init__(self, model: TinyMLP):
        self.model = model

    def infer(self, batch: list[list[float]]) -> list[list[float]]:
        m = self.model
        _check_inputs(m, batch)
        hidden = [[v for v in m.b1] for _ in batch]
        for i in range(m.input_dim):
            weights = m.w1[i]
            for n, row in enumerate(batch):
                x = row[i]
                for j in range(m.hidden_dim):
                    hidden[n][j] += x * weights[j]
        for row in hidden:
            for j in range(m.hidden_dim):
                row[j] = max(0.0, row[j])
        outputs = [[v for v in m.b2] for _ in batch]
        for j in range(m.hidden_dim):
            weights = m.w2[j]
            for n, row in enumerate(hidden):
                h = row[j]
                for k in range(m.output_dim):
                    outputs[n][k] += h * weights[k]
        return outputs


class NumpyEngine:
    """Optional vectorized CPU execution path; installation not required."""
    name = "numpy_matmul"

    def __init__(self, model: TinyMLP):
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Optional backend requires: pip install -e '.[compute-numpy]'") from exc
        self.np = np
        self.model = model
        self.w1 = np.asarray(model.w1, dtype=np.float64)
        self.b1 = np.asarray(model.b1, dtype=np.float64)
        self.w2 = np.asarray(model.w2, dtype=np.float64)
        self.b2 = np.asarray(model.b2, dtype=np.float64)

    def infer(self, batch: list[list[float]]) -> list[list[float]]:
        _check_inputs(self.model, batch)
        np = self.np
        x = np.asarray(batch, dtype=np.float64)
        h = np.maximum(x @ self.w1 + self.b1, 0.0)
        return (h @ self.w2 + self.b2).tolist()


def compare_outputs(expected: list[list[float]], actual: list[list[float]], atol: float = 1e-9, rtol: float = 1e-7) -> dict:
    if atol < 0 or rtol < 0 or not math.isfinite(atol + rtol):
        raise ValueError("Tolerances must be finite and nonnegative")
    if len(expected) != len(actual) or any(len(a) != len(b) for a, b in zip(expected, actual)):
        return {"passed": False, "max_abs_error": None, "failed_elements": None, "reason": "shape mismatch"}
    errors = [(a, b) for row1, row2 in zip(expected, actual) for a, b in zip(row1, row2)]
    if any(not math.isfinite(a) or not math.isfinite(b) for a, b in errors):
        return {"passed": False, "max_abs_error": None, "failed_elements": None, "reason": "nonfinite output"}
    fails = sum(abs(a - b) > atol + rtol * abs(a) for a, b in errors)
    return {"passed": fails == 0, "max_abs_error": max((abs(a - b) for a, b in errors), default=0.0), "failed_elements": fails, "reason": None}


def benchmark(engines: list[Engine], batch: list[list[float]], warmup: int = 3, repeats: int = 15) -> dict:
    if warmup < 0 or not 1 <= repeats <= 10000:
        raise ValueError("Invalid warmup/repeats")
    if not engines or engines[0].name != "python_reference":
        raise ValueError("Reference engine must be first")
    reference = engines[0].infer(batch)
    entries = []
    for engine in engines:
        output = engine.infer(batch)
        correctness = compare_outputs(reference, output, atol=getattr(engine, "atol", 1e-9), rtol=getattr(engine, "rtol", 1e-7))
        for _ in range(warmup):
            engine.infer(batch)
        timings = []
        for _ in range(repeats):
            start = time.perf_counter()
            engine.infer(batch)
            timings.append(time.perf_counter() - start)
        entries.append({"engine": engine.name, "median_ms": median_ms(timings), "p95_ms": percentile_ms(timings, 95), "correctness": correctness, "tolerance": {"atol": getattr(engine, "atol", 1e-9), "rtol": getattr(engine, "rtol", 1e-7)}, "runtime_versions": getattr(engine, "versions", None)})
    baseline = entries[0]["median_ms"]
    for entry in entries:
        entry["speedup_vs_reference"] = round(baseline / entry["median_ms"], 4) if entry["median_ms"] else None
    return {"project": "trinity_compute", "scenario": "synthetic_tiny_mlp_float64_cpu", "batch_size": len(batch), "warmup": warmup, "repeats": repeats, "engines": entries, "environment": metadata(), "caveat": "Synthetic CPU toy model only; not a general AI accelerator or model portability claim."}
