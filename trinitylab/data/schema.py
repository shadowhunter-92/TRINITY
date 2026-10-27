"""Simple structural compatibility gate; intentionally not a full schema registry."""
from __future__ import annotations

import json
import re
from pathlib import Path

TYPES = {"string", "bool", "int32", "int64", "float64"}
WIDEN = {("int32", "int64"), ("int32", "float64")}


def parse_schema(data: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("fields"), list) or not 1 <= len(data["fields"]) <= 1000:
        raise ValueError("Schema must have 1 to 1000 fields")
    result = {}
    for field in data["fields"]:
        if not isinstance(field, dict):
            raise ValueError("Invalid field")
        name, kind, nullable = field.get("name"), field.get("type"), field.get("nullable")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", name):
            raise ValueError("Invalid field name")
        if name in result or kind not in TYPES or type(nullable) is not bool:
            raise ValueError("Duplicate field or invalid type/nullable")
        result[name] = {"type": kind, "nullable": nullable}
    return result


def load_schema(path: str) -> dict:
    return parse_schema(json.loads(Path(path).read_text(encoding="utf-8")))


def compare_schemas(old: dict, new: dict) -> dict:
    """Can the new schema ingest all values valid under the old schema?

    Only exactly representable built-in numerical widenings are allowed.
    In particular int64 -> float64 is disallowed due to precision loss.
    """
    issues = []
    for field, previous in old.items():
        current = new.get(field)
        if current is None:
            issues.append({"field": field, "reason": "required_existing_field_removed"})
            continue
        if previous["type"] != current["type"] and (previous["type"], current["type"]) not in WIDEN:
            issues.append({"field": field, "reason": "incompatible_type_change", "from": previous["type"], "to": current["type"]})
        if previous["nullable"] and not current["nullable"]:
            issues.append({"field": field, "reason": "nullable_became_required"})
    for field, current in new.items():
        if field not in old and not current["nullable"]:
            issues.append({"field": field, "reason": "new_nonnullable_field"})
    return {"project": "trinity_data", "compatibility_rule": "new_schema_can_accept_old_rows", "compatible": not issues, "issues": issues, "added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()), "note": "Structural only: does not validate semantic meaning, constraints, column order or precision."}
