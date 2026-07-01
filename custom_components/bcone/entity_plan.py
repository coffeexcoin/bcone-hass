"""Entity-plan helpers for BCone read-only entities."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ENTITY_PLAN_PATH = Path(__file__).with_name("entity_plan.json")


def entities_for_platform(platform: str) -> list[dict[str, Any]]:
    """Return read-only entity definitions for a Home Assistant platform."""

    plan = json.loads(ENTITY_PLAN_PATH.read_text(encoding="utf-8"))
    return [
        entity
        for entity in plan.get("entities", [])
        if entity.get("platform") == platform and entity.get("read_only") is True
    ]


def private_state(report: dict[str, Any]) -> dict[str, Any]:
    """Return the private normalized state from a state report."""

    snapshot = report.get("final_snapshot") if isinstance(report.get("final_snapshot"), dict) else {}
    state = snapshot.get("private_entity_state")
    return state if isinstance(state, dict) else {}


def pool_unit_ids(report: dict[str, Any]) -> list[str]:
    """Return stable pool-unit IDs present in the latest state report."""

    units = private_state(report).get("pool_units")
    if not isinstance(units, dict):
        return []
    return sorted(str(unit_id) for unit_id in units)


def unseen_pool_unit_ids(report: dict[str, Any], seen: set[str]) -> list[str]:
    """Return pool-unit IDs that do not have entities yet."""

    return [unit_id for unit_id in pool_unit_ids(report) if unit_id not in seen]


def value_from_report(report: dict[str, Any], source_path: str, pool_unit_id: str | None = None) -> Any:
    """Resolve a generated entity-plan source path against a state report."""

    if source_path.startswith("report."):
        return _report_value(report, source_path.removeprefix("report."))

    state = private_state(report)
    if source_path.startswith("state.pool_units[*]."):
        if pool_unit_id is None:
            return None
        units = state.get("pool_units")
        unit = units.get(pool_unit_id) if isinstance(units, dict) else None
        if not isinstance(unit, dict):
            return None
        return unit.get(source_path.rsplit(".", 1)[1])

    if not source_path.startswith("state."):
        return None

    value: Any = state
    for part in source_path.removeprefix("state.").split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def bool_from_report(report: dict[str, Any], source_path: str, pool_unit_id: str | None = None) -> bool | None:
    """Resolve a source path and coerce known BCone truthy/falsey values."""

    value = value_from_report(report, source_path, pool_unit_id=pool_unit_id)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return None


def timestamp_from_report(report: dict[str, Any], source_path: str) -> datetime | None:
    """Resolve an ISO-8601 timestamp source path as a timezone-aware datetime."""

    value = value_from_report(report, source_path)
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def entity_available(report: dict[str, Any], scope: str, source_path: str, pool_unit_id: str | None = None) -> bool:
    """Return HA availability for monitor versus decoded device-state entities."""

    if scope == "monitor":
        return bool(report)
    if report.get("error_type"):
        return False
    return value_from_report(report, source_path, pool_unit_id=pool_unit_id) is not None


def device_info_from_report(
    report: dict[str, Any],
    *,
    entry_id: str,
    domain: str,
    pool_unit_id: str | None = None,
) -> dict[str, Any]:
    """Build Home Assistant device metadata from the latest normalized state."""

    state = private_state(report)
    device_id = state.get("device_id") if isinstance(state.get("device_id"), str) else entry_id
    if pool_unit_id is not None:
        return _pool_unit_device_info(state, domain=domain, hub_device_id=device_id, pool_unit_id=pool_unit_id)

    name = state.get("system_name") if isinstance(state.get("system_name"), str) else "BCone"
    info: dict[str, Any] = {
        "identifiers": {(domain, device_id)},
        "manufacturer": "Lifebuoy",
        "name": name,
    }
    firmware = state.get("firmware_version")
    if isinstance(firmware, str) and firmware:
        info["sw_version"] = firmware
    return info


def _pool_unit_device_info(
    state: dict[str, Any],
    *,
    domain: str,
    hub_device_id: str,
    pool_unit_id: str,
) -> dict[str, Any]:
    units = state.get("pool_units")
    unit = units.get(pool_unit_id) if isinstance(units, dict) else None
    unit = unit if isinstance(unit, dict) else {}
    unit_name = unit.get("name")
    serial = unit.get("serial")
    firmware = unit.get("firmware_version")
    info: dict[str, Any] = {
        "identifiers": {(domain, f"{hub_device_id}:pool_unit:{pool_unit_id}")},
        "manufacturer": "Lifebuoy",
        "name": _pool_unit_device_name(unit_name, pool_unit_id),
        "via_device": (domain, hub_device_id),
    }
    if isinstance(serial, str) and serial:
        info["serial_number"] = serial
    if isinstance(firmware, str) and firmware:
        info["sw_version"] = firmware
    return info


def _pool_unit_device_name(unit_name: Any, pool_unit_id: str) -> str:
    """Return a device-level name for one floating pool unit."""

    if isinstance(unit_name, str) and unit_name.strip():
        return unit_name.strip()
    return f"Pool Unit {pool_unit_id}"


def _report_value(report: dict[str, Any], path: str) -> Any:
    computed = {
        "seeded_startup": False,
        "subscription_ack_count": 0,
        "update_count": len(report.get("updates") or []),
    }
    if path in computed:
        return computed[path]

    value: Any = report
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value
