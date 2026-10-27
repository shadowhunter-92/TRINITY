"""Reproducible, standard-library-only reporting helpers."""
from __future__ import annotations

import json
import math
import os
import platform
import statistics
import sys
from pathlib import Path


def metadata() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "not reported",
        "pid_is_recorded": False,
        "cpu_count": os.cpu_count(),
    }


def median_ms(values_sec: list[float]) -> float:
    if not values_sec:
        raise ValueError("At least one timing sample required")
    return round(statistics.median(values_sec) * 1000, 6)


def percentile_ms(values_sec: list[float], percent: int) -> float:
    if not values_sec or not 0 <= percent <= 100:
        raise ValueError("Invalid percentile or empty samples")
    ordered = sorted(values_sec)
    p = (len(ordered) - 1) * percent / 100
    a, b = math.floor(p), math.ceil(p)
    return round((ordered[a] * (b - p) + ordered[b] * (p - a)) * 1000, 6) if a != b else round(ordered[a] * 1000, 6)


def emit(payload: dict, output: str | None = None) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
