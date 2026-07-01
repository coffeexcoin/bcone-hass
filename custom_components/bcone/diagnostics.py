"""Redacted diagnostics for the BCone read-only integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .const import DOMAIN

ENTITY_PLAN_PATH = Path(__file__).with_name("entity_plan.json")


async def async_get_config_entry_diagnostics(hass: Any, entry: Any) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""

    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    report = getattr(coordinator, "data", None) if coordinator is not None else None
    return build_diagnostics(report if isinstance(report, dict) else {})


def build_diagnostics(report: dict[str, Any], *, entity_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build diagnostics without exposing private normalized state values."""

    final = report.get("final_snapshot") if isinstance(report.get("final_snapshot"), dict) else {}
    safety = report.get("safety") if isinstance(report.get("safety"), dict) else {}
    plan = entity_plan if entity_plan is not None else _load_entity_plan()
    entities = plan.get("entities") if isinstance(plan.get("entities"), list) else []
    return {
        "scope": "auth-and-readonly-monitoring",
        "ready": _ready(report, entities),
        "transport": {
            "source": report.get("source"),
            "cloud_connected": bool(report.get("cloud_connected")),
            "mqtt_connected": bool(report.get("mqtt_connected")),
            "mqtt_credentials_present": bool(report.get("mqtt_credentials_present")),
            "mqtt_endpoint": report.get("mqtt_endpoint"),
            "mqtt_port": report.get("mqtt_port"),
            "mqtt_topics": _redact_topics(_strings(report.get("mqtt_topics"))),
            "mqtt_error_type": report.get("mqtt_error_type"),
            "error_type": report.get("error_type"),
            "failed_phase": report.get("failed_phase"),
        },
        "safety": {
            "passive_only": safety.get("passive_only") is True,
            "publishes_requested": safety.get("publishes_requested") is True,
            "state_changing": safety.get("state_changing") is True,
        },
        "runtime": {
            "generated_at_utc": report.get("generated_at_utc"),
            "history_item_count": int(report.get("history_item_count") or 0),
            "mqtt_update_count": int(report.get("mqtt_update_count") or 0),
            "update_count": len(report.get("updates") or []),
        },
        "state_surface": {
            "fields_present": _strings(final.get("fields_present")),
            "pool_unit_count": int(final.get("pool_unit_count") or 0),
            "pool_unit_fields": _strings(final.get("pool_unit_fields")),
            "schedule_fields_present": _strings(final.get("schedule_fields_present")),
        },
        "entity_plan": {
            "entity_count": len(entities),
            "monitor_entity_count": _scope_count(entities, "monitor"),
            "device_state_entity_count": _scope_count(entities, "hub")
            + _scope_count(entities, "pool_unit")
            + _scope_count(entities, "schedule"),
            "platforms": sorted({str(entity.get("platform")) for entity in entities if isinstance(entity, dict)}),
        },
        "limitations": _limitations(report),
    }


def _ready(report: dict[str, Any], entities: list[Any]) -> bool:
    return (
        bool(report.get("cloud_connected"))
        and report.get("safety", {}).get("passive_only") is True
        and report.get("safety", {}).get("publishes_requested") is False
        and bool(report.get("final_snapshot", {}).get("fields_present"))
        and bool(entities)
    )


def _load_entity_plan() -> dict[str, Any]:
    try:
        parsed = json.loads(ENTITY_PLAN_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _scope_count(entities: list[Any], scope: str) -> int:
    return sum(1 for entity in entities if isinstance(entity, dict) and entity.get("scope") == scope)


def _limitations(report: dict[str, Any]) -> list[str]:
    limitations = []
    if not report.get("updates"):
        limitations.append("latest refresh had no device-history state items")
    if report.get("error_type"):
        limitations.append("latest refresh failed before a complete read-only state report")
    if not report.get("mqtt_credentials_present"):
        limitations.append("optional MQTT credentials are not present; REST history is the read-only source")
    elif not report.get("mqtt_connected"):
        limitations.append("optional MQTT credentials are present, but the latest MQTT connection is not active")
    limitations.append("control, configuration writes, and firmware actions are outside V1")
    return limitations


def _redact_topics(topics: list[str]) -> list[str]:
    return [_redact_topic(topic) for topic in topics]


def _redact_topic(topic: str) -> str:
    if topic.startswith("bc/"):
        parts = topic.split("/")
        if len(parts) >= 3:
            return "bc/<device_id>/" + "/".join(parts[2:])
    return topic


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(str(item) for item in value)
