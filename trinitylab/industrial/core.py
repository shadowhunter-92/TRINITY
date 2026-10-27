"""Read-only industrial signal mapping, quality checks, and deterministic drift detection."""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path

from trinitylab.util import median_ms, metadata


@dataclass(frozen=True)
class Signal:
    signal_id: str
    address: int
    unit: str
    scale: float
    offset: float
    minimum: float
    maximum: float
    register_type: str = "holding"


@dataclass(frozen=True)
class Profile:
    machine_id: str
    version: int
    signals: tuple[Signal, ...]


def parse_profile(data: dict) -> Profile:
    if not isinstance(data, dict):
        raise ValueError("Profile must be an object")
    machine_id = data.get("machine_id")
    version = data.get("version")
    if not isinstance(machine_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", machine_id):
        raise ValueError("Unsafe/invalid machine_id")
    if type(version) is not int or version < 1:
        raise ValueError("version must be a positive integer")
    raw_signals = data.get("signals")
    if not isinstance(raw_signals, list) or not 1 <= len(raw_signals) <= 2000:
        raise ValueError("signals must contain 1 to 2000 entries")
    signals = []
    ids = set()
    for raw in raw_signals:
        if not isinstance(raw, dict):
            raise ValueError("Each signal must be an object")
        signal_id, address = raw.get("signal_id"), raw.get("address")
        unit = raw.get("unit", "")
        kind = raw.get("register_type", "holding")
        if not isinstance(signal_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}", signal_id):
            raise ValueError("Invalid signal_id")
        if signal_id in ids:
            raise ValueError("Duplicate signal_id")
        ids.add(signal_id)
        if type(address) is not int or not 0 <= address <= 65535:
            raise ValueError("register address must be 0..65535")
        if not isinstance(unit, str) or len(unit) > 32 or any(ord(c) < 32 for c in unit):
            raise ValueError("Invalid unit")
        if kind not in ("holding", "input"):
            raise ValueError("register_type must be 'holding' or 'input'")
        numbers = []
        for key, default in [("scale", 1), ("offset", 0), ("minimum", -1e10), ("maximum", 1e10)]:
            v = raw.get(key, default)
            if type(v) not in (int, float) or not math.isfinite(v):
                raise ValueError(f"Invalid numeric {key}")
            numbers.append(float(v))
        if numbers[2] > numbers[3]:
            raise ValueError("minimum exceeds maximum")
        signals.append(Signal(signal_id, address, unit, *numbers, register_type=kind))
    return Profile(machine_id, version, tuple(signals))


def load_profile(path: str | Path) -> Profile:
    return parse_profile(json.loads(Path(path).read_text(encoding="utf-8")))


def load_registers(path: str | Path) -> dict[int, int]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or len(data) > 65536:
        raise ValueError("Register fixture must be a bounded object")
    result = {}
    for k, value in data.items():
        if not isinstance(k, str) or not k.isdecimal():
            raise ValueError("Register keys must be decimal addresses")
        address = int(k)
        if not 0 <= address <= 65535 or type(value) is not int or not 0 <= value <= 65535:
            raise ValueError("Registers must be 16-bit unsigned integers")
        result[address] = value
    return result


def snapshot(profile: Profile, registers: dict[int, int], captured_at: str = "SIMULATED") -> dict:
    records = []
    for signal in profile.signals:
        raw = registers.get(signal.address)
        if raw is None:
            records.append({"signal_id": signal.signal_id, "address": signal.address, "value": None, "unit": signal.unit, "quality": "missing"})
            continue
        if type(raw) is not int or not 0 <= raw <= 65535:
            raise ValueError("Invalid register value")
        value = raw * signal.scale + signal.offset
        quality = "good" if math.isfinite(value) and signal.minimum <= value <= signal.maximum else "out_of_range"
        records.append({"signal_id": signal.signal_id, "address": signal.address, "raw": raw, "value": value, "unit": signal.unit, "quality": quality})
    return {"project": "trinity_industrial", "machine_id": profile.machine_id, "profile_version": profile.version, "captured_at": captured_at, "source": "simulated_fixture_or_explicit_read", "signals": records}


def drift(old: Profile, new: Profile) -> dict:
    if old.machine_id != new.machine_id:
        raise ValueError("Cannot compare different machines")
    if new.version <= old.version:
        raise ValueError("New profile version must increase")
    before = {s.signal_id: s for s in old.signals}
    after = {s.signal_id: s for s in new.signals}
    changes = []
    for signal_id in sorted(before.keys() | after.keys()):
        a, b = before.get(signal_id), after.get(signal_id)
        if a is None:
            changes.append({"signal_id": signal_id, "type": "added"})
        elif b is None:
            changes.append({"signal_id": signal_id, "type": "removed"})
        else:
            fields = {}
            for attr in ("address", "register_type", "unit", "scale", "offset", "minimum", "maximum"):
                if getattr(a, attr) != getattr(b, attr):
                    fields[attr] = {"old": getattr(a, attr), "new": getattr(b, attr)}
            if fields:
                changes.append({"signal_id": signal_id, "type": "modified", "fields": fields})
    return {"project": "trinity_industrial", "machine_id": old.machine_id, "from_version": old.version, "to_version": new.version, "drift_detected": bool(changes), "changes": changes}


def benchmark(profile: Profile, registers: dict[int, int], repeats: int = 1000) -> dict:
    if not 1 <= repeats <= 100000:
        raise ValueError("repeats must be 1..100000")
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = snapshot(profile, registers)
        timings.append(time.perf_counter() - start)
    return {"project": "trinity_industrial", "scenario": "in_memory_snapshot_only", "signals": len(profile.signals), "repeats": repeats, "median_ms": median_ms(timings), "quality_counts": {kind: sum(r["quality"] == kind for r in result["signals"]) for kind in ("good", "missing", "out_of_range")}, "environment": metadata(), "caveat": "No PLC, network, OPC UA, SCADA, or production safety performance measured."}
