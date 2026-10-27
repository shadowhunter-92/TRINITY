"""Restricted, opt-in OPC UA *read-only* laboratory adapter.

Only explicit 127.0.0.1 endpoints are accepted. No discovery, browsing, writes,
subscriptions, control commands, credentials, or remote connections are supported.
The optional ``asyncua`` dependency is imported only after consent validation.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


class OPCUAError(Exception):
    """Bounded OPC UA laboratory client error."""


@dataclass(frozen=True)
class UASignal:
    signal_id: str
    identifier: str
    unit: str
    scale: float
    offset: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class UAProfile:
    machine_id: str
    version: int
    namespace_uri: str
    signals: tuple[UASignal, ...]


def parse_opcua_profile(data: dict) -> UAProfile:
    """Validate a strictly bounded JSON profile; identifiers are string NodeIds."""
    if not isinstance(data, dict):
        raise ValueError("OPC UA profile must be a JSON object")
    machine_id = data.get("machine_id")
    version = data.get("version")
    namespace = data.get("namespace_uri")
    signals = data.get("signals")
    if not isinstance(machine_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", machine_id):
        raise ValueError("Invalid machine_id")
    if type(version) is not int or version < 1:
        raise ValueError("Invalid profile version")
    if not isinstance(namespace, str) or not re.fullmatch(r"urn:[A-Za-z0-9:_.-]{3,120}", namespace):
        raise ValueError("Invalid namespace URI")
    if not isinstance(signals, list) or not 1 <= len(signals) <= 128:
        raise ValueError("Expected 1..128 signals")
    parsed = []
    seen_ids, seen_nodes = set(), set()
    for item in signals:
        if not isinstance(item, dict):
            raise ValueError("Signal must be an object")
        sid, identifier, unit = item.get("signal_id"), item.get("identifier"), item.get("unit", "")
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}", sid):
            raise ValueError("Invalid signal_id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}", identifier):
            raise ValueError("Invalid NodeId identifier")
        if not isinstance(unit, str) or len(unit) > 32 or any(ord(c) < 32 for c in unit):
            raise ValueError("Invalid unit")
        if sid in seen_ids or identifier in seen_nodes:
            raise ValueError("Duplicate signal or NodeId")
        seen_ids.add(sid)
        seen_nodes.add(identifier)
        values = []
        for key, default in (("scale", 1), ("offset", 0), ("minimum", -1e10), ("maximum", 1e10)):
            value = item.get(key, default)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"Invalid {key}")
            values.append(float(value))
        if values[2] > values[3]:
            raise ValueError("minimum exceeds maximum")
        parsed.append(UASignal(sid, identifier, unit, *values))
    return UAProfile(machine_id, version, namespace, tuple(parsed))


def load_opcua_profile(path: str | Path) -> UAProfile:
    return parse_opcua_profile(json.loads(Path(path).read_text(encoding="utf-8")))


def opcua_profile_drift(old: UAProfile, new: UAProfile) -> dict:
    if old.machine_id != new.machine_id or new.version <= old.version:
        raise ValueError("Different machine or non-incrementing version")
    changes = []
    if old.namespace_uri != new.namespace_uri:
        changes.append({"type": "namespace_changed", "old": old.namespace_uri, "new": new.namespace_uri})
    before = {s.signal_id: s for s in old.signals}
    after = {s.signal_id: s for s in new.signals}
    for sid in sorted(before.keys() | after.keys()):
        if sid not in before:
            changes.append({"type": "added", "signal_id": sid})
        elif sid not in after:
            changes.append({"type": "removed", "signal_id": sid})
        else:
            delta = {key: {"old": getattr(before[sid], key), "new": getattr(after[sid], key)}
                     for key in ("identifier", "unit", "scale", "offset", "minimum", "maximum")
                     if getattr(before[sid], key) != getattr(after[sid], key)}
            if delta:
                changes.append({"type": "modified", "signal_id": sid, "fields": delta})
    return {"machine_id": old.machine_id, "from_version": old.version,
            "to_version": new.version, "drift_detected": bool(changes), "changes": changes}


def validate_lab_endpoint(endpoint: str) -> str:
    """Enforce numeric loopback only: no DNS or remote address is ever accepted."""
    if not isinstance(endpoint, str) or not 1 <= len(endpoint) <= 256:
        raise ValueError("Invalid endpoint")
    try:
        url = urlsplit(endpoint)
        port = url.port
    except ValueError as exc:
        raise ValueError("Invalid OPC UA endpoint") from exc
    if (url.scheme != "opc.tcp" or url.hostname != "127.0.0.1" or not port
            or url.username is not None or url.password is not None
            or url.query or url.fragment or not endpoint.startswith("opc.tcp://127.0.0.1:")):
        raise PermissionError("Only numeric IPv4 loopback OPC UA endpoints are permitted")
    return endpoint


def _timestamp_string(value: object) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return None


def evaluate_datavalue(signal: UASignal, dv: object) -> dict:
    """Convert one server DataValue to a safe, typed measurement record."""
    record = {"signal_id": signal.signal_id, "node_identifier": signal.identifier,
              "unit": signal.unit, "value": None, "quality": "bad_status", "source_timestamp": None}
    if dv is None:
        record["quality"] = "missing"
        return record
    stamp = getattr(dv, "SourceTimestamp", None)
    record["source_timestamp"] = _timestamp_string(stamp)
    code = getattr(dv, "StatusCode", None)
    if code is None or not callable(getattr(code, "is_good", None)) or not code.is_good():
        return record
    variant = getattr(dv, "Value", None)
    raw = getattr(variant, "Value", None)
    if type(raw) not in (float, int) or not math.isfinite(raw):
        record["quality"] = "invalid_type"
        return record
    value = raw * signal.scale + signal.offset
    if not math.isfinite(value):
        record["quality"] = "invalid_type"
    elif not signal.minimum <= value <= signal.maximum:
        record.update(value=value, quality="out_of_range")
    else:
        record.update(value=value, quality="good")
    return record


async def read_opcua_snapshot(profile: UAProfile, endpoint: str, *,
                              enable_network: bool = False, timeout: float = 2.0) -> dict:
    """Perform one bounded, explicit *read-only* loopback snapshot.

    A fresh session is used for every call. Reconnect means calling this function
    again; automatic retries are intentionally excluded to avoid hidden traffic.
    """
    if not enable_network:
        raise PermissionError("OPC UA networking disabled: opt in with enable_network=True")
    validate_lab_endpoint(endpoint)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0.1 <= timeout <= 10:
        raise ValueError("Timeout must be within 0.1..10 seconds")
    if not isinstance(profile, UAProfile) or not 1 <= len(profile.signals) <= 128:
        raise ValueError("Invalid profile")
    try:
        from asyncua import Client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise OPCUAError('Optional OPC UA library missing; install pip install ".[industrial-opcua]"') from exc

    async def _fetch() -> list[dict]:
        async with Client(url=endpoint, timeout=timeout) as client:
            ns = await asyncio.wait_for(client.get_namespace_index(profile.namespace_uri), timeout)
            if type(ns) is not int or not 1 <= ns <= 65535:
                raise OPCUAError("OPC UA namespace index was invalid")
            records = []
            for signal in profile.signals:
                node = client.get_node(f"ns={ns};s={signal.identifier}")
                try:
                    dv = await asyncio.wait_for(node.read_data_value(), timeout)
                except Exception as exc:
                    # Per-signal failure is represented as a bounded quality flag.
                    # Never expose network/server exception details in client output.
                    quality = "timeout" if isinstance(exc, asyncio.TimeoutError) else "read_error"
                    records.append({"signal_id": signal.signal_id, "node_identifier": signal.identifier,
                                    "unit": signal.unit, "value": None, "quality": quality,
                                    "source_timestamp": None})
                    continue
                records.append(evaluate_datavalue(signal, dv))
            return records

    try:
        # Timeout covers session establishment and all reads, not only each node.
        signals = await asyncio.wait_for(_fetch(), timeout * (len(profile.signals) + 2))
    except asyncio.TimeoutError as exc:
        raise OPCUAError("OPC UA request deadline exceeded") from exc
    except OPCUAError:
        raise
    except Exception as exc:
        raise OPCUAError(f"OPC UA session failed ({type(exc).__name__})") from exc
    return {"project": "trinity_industrial", "source": "opcua_explicit_local_read",
            "machine_id": profile.machine_id, "profile_version": profile.version,
            "captured_at": datetime.now(timezone.utc).isoformat(), "signals": signals}
