"""Normalize BCone history/MQTT-shaped payloads into HA entity state."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from .const import BCONE_MQTT_ENDPOINT, BCONE_MQTT_PORT


@dataclass(frozen=True, slots=True)
class PoolUnitState:
    """Normalized BCone pool unit state."""

    puid: str | None = None
    serial: str | None = None
    name: str | None = None
    mac: str | None = None
    state: str | None = None
    sensitivity: float | None = None
    alarms: str | None = None
    battery: float | None = None
    battery_state: str | None = None
    rssi: int | None = None
    temperature: int | None = None
    position: str | None = None
    light: str | None = None
    firmware_version: str | None = None
    firmware_upgrading: bool | None = None
    keepalive_sent: int | None = None
    keepalive_missed: int | None = None
    keepalive_failed: int | None = None
    last_keepalive_miss_count: int | None = None
    last_keepalive_fail_count: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class BconeStateSnapshot:
    """Current normalized state for HA entities."""

    device_id: str | None = None
    system_name: str | None = None
    alarm_active: bool | None = None
    notification_text: str | None = None
    hub_serial: str | None = None
    hub_timestamp: int | None = None
    firmware_upgrading: bool | None = None
    firmware_version: str | None = None
    firmware_source: str | None = None
    firmware_status_marker: str | None = None
    hub_battery: float | None = None
    hub_battery_state: str | None = None
    charging_state: str | None = None
    hub_rssi: int | None = None
    wifi_rssi: int | None = None
    hub_clock: str | None = None
    timezone_offset_minutes: int | None = None
    hub_flags: dict[str, str | None] = field(default_factory=dict)
    primary_pool_unit_state: str | None = None
    sensitivities: tuple[float, ...] = ()
    pool_unit_batteries: tuple[float, ...] = ()
    pool_unit_battery_states: tuple[str, ...] = ()
    pool_unit_rssi: tuple[int, ...] = ()
    pool_unit_temperatures: tuple[int, ...] = ()
    pool_unit_positions: tuple[str, ...] = ()
    pool_unit_lights: tuple[str, ...] = ()
    pool_unit_serials: tuple[str, ...] = ()
    pool_unit_firmware_versions: tuple[str, ...] = ()
    pool_unit_diagnostics: tuple[dict[str, int | None], ...] = ()
    schedules: dict[str, int | str | None] = field(default_factory=dict)
    pool_units: dict[str, PoolUnitState] = field(default_factory=dict)

    def as_entity_state(self) -> dict[str, Any]:
        """Return a stable JSON-serializable state view."""

        return {
            "device_id": self.device_id,
            "system_name": self.system_name,
            "alarm_active": self.alarm_active,
            "notification_text": self.notification_text,
            "hub_serial": self.hub_serial,
            "hub_timestamp": self.hub_timestamp,
            "firmware_upgrading": self.firmware_upgrading,
            "firmware_version": self.firmware_version,
            "firmware_source": self.firmware_source,
            "firmware_status_marker": self.firmware_status_marker,
            "hub_battery": self.hub_battery,
            "hub_battery_state": self.hub_battery_state,
            "charging_state": self.charging_state,
            "hub_rssi": self.hub_rssi,
            "wifi_rssi": self.wifi_rssi,
            "hub_clock": self.hub_clock,
            "timezone_offset_minutes": self.timezone_offset_minutes,
            "hub_flags": dict(self.hub_flags),
            "primary_pool_unit_state": self.primary_pool_unit_state,
            "sensitivities": list(self.sensitivities),
            "pool_unit_batteries": list(self.pool_unit_batteries),
            "pool_unit_battery_states": list(self.pool_unit_battery_states),
            "pool_unit_rssi": list(self.pool_unit_rssi),
            "pool_unit_temperatures": list(self.pool_unit_temperatures),
            "pool_unit_positions": list(self.pool_unit_positions),
            "pool_unit_lights": list(self.pool_unit_lights),
            "pool_unit_serials": list(self.pool_unit_serials),
            "pool_unit_firmware_versions": list(self.pool_unit_firmware_versions),
            "pool_unit_diagnostics": [dict(item) for item in self.pool_unit_diagnostics],
            "schedules": dict(self.schedules),
            "pool_units": {
                key: {field: value for field, value in asdict(unit).items() if field != "raw"}
                for key, unit in sorted(self.pool_units.items())
            },
        }


class BconeStateStore:
    """Merge BCone state payloads into a current snapshot."""

    def __init__(self) -> None:
        self._snapshot = BconeStateSnapshot()

    @property
    def snapshot(self) -> BconeStateSnapshot:
        """Return the current snapshot."""

        return self._snapshot

    def apply_payload(self, payload: dict[str, Any]) -> BconeStateSnapshot:
        """Apply a history item or live indication-shaped payload."""

        body = _payload_dict(payload)
        state = body.get("data") if isinstance(body.get("data"), dict) else body
        pool_units = tuple(_pool_unit(item) for item in _pool_unit_items(state, body))
        previous = self._snapshot
        merged_units = dict(previous.pool_units)
        for index, unit in enumerate(pool_units):
            key = unit.puid or unit.mac or f"index:{index}"
            merged_units[key] = _merge_unit(merged_units.get(key), unit)
        hub_battery = _as_voltage(state.get("hubatt") or state.get("hubattery"))

        self._snapshot = replace(
            previous,
            device_id=_as_str(state.get("DeviceID") or body.get("deviceId")) or previous.device_id,
            system_name=_as_str(state.get("sysname")) or previous.system_name,
            alarm_active=_alarm_active(state, body, pool_units)
            if _alarm_active(state, body, pool_units) is not None
            else previous.alarm_active,
            notification_text=_as_str(state.get("notificationText") or body.get("notificationText"))
            or previous.notification_text,
            hub_serial=_as_str(state.get("sn")) or previous.hub_serial,
            hub_timestamp=_as_int(state.get("timestamp")) if _as_int(state.get("timestamp")) is not None else previous.hub_timestamp,
            firmware_upgrading=_as_bool(state.get("isUpg"))
            if _as_bool(state.get("isUpg")) is not None
            else previous.firmware_upgrading,
            firmware_version=_as_str(state.get("v")) or previous.firmware_version,
            firmware_source=_as_str(state.get("src")) or previous.firmware_source,
            firmware_status_marker=_as_str(state.get("top3")) or previous.firmware_status_marker,
            hub_battery=hub_battery if hub_battery is not None else previous.hub_battery,
            hub_battery_state=_as_str(state.get("hubattSt") or state.get("hubattState")) or previous.hub_battery_state,
            charging_state=_as_str(state.get("chargingstate") or state.get("chst")) or previous.charging_state,
            hub_rssi=_as_int(state.get("HUrssi")) if _as_int(state.get("HUrssi")) is not None else previous.hub_rssi,
            wifi_rssi=_as_int(state.get("WifiRssi")) if _as_int(state.get("WifiRssi")) is not None else previous.wifi_rssi,
            hub_clock=_as_hub_clock(state.get("time")) or previous.hub_clock,
            timezone_offset_minutes=_as_int(state.get("gmtof"))
            if _as_int(state.get("gmtof")) is not None
            else previous.timezone_offset_minutes,
            hub_flags=_merge_non_none(previous.hub_flags, {key: _as_str(state.get(key)) for key in ("hb", "hs", "lb", "ps")}),
            primary_pool_unit_state=next((unit.state for unit in pool_units if unit.state is not None), None)
            or previous.primary_pool_unit_state,
            sensitivities=tuple(unit.sensitivity for unit in pool_units if unit.sensitivity is not None)
            or previous.sensitivities,
            pool_unit_batteries=tuple(unit.battery for unit in pool_units if unit.battery is not None)
            or previous.pool_unit_batteries,
            pool_unit_battery_states=tuple(unit.battery_state for unit in pool_units if unit.battery_state is not None)
            or previous.pool_unit_battery_states,
            pool_unit_rssi=tuple(unit.rssi for unit in pool_units if unit.rssi is not None) or previous.pool_unit_rssi,
            pool_unit_temperatures=tuple(unit.temperature for unit in pool_units if unit.temperature is not None)
            or previous.pool_unit_temperatures,
            pool_unit_positions=tuple(unit.position for unit in pool_units if unit.position is not None)
            or previous.pool_unit_positions,
            pool_unit_lights=tuple(unit.light for unit in pool_units if unit.light is not None) or previous.pool_unit_lights,
            pool_unit_serials=tuple(unit.serial for unit in pool_units if unit.serial is not None)
            or previous.pool_unit_serials,
            pool_unit_firmware_versions=tuple(
                unit.firmware_version for unit in pool_units if unit.firmware_version is not None
            )
            or previous.pool_unit_firmware_versions,
            pool_unit_diagnostics=tuple(diagnostics for unit in pool_units if (diagnostics := _pool_unit_diagnostics(unit)))
            or previous.pool_unit_diagnostics,
            schedules=_merge_non_none(
                previous.schedules,
                {
                    "dndstart": _as_dnd_time(state.get("dndstart")),
                    "dndstop": _as_dnd_time(state.get("dndstop")),
                    "dndstart2": _as_dnd_time(state.get("dndstart2")),
                    "dndstop2": _as_dnd_time(state.get("dndstop2")),
                    "dndstart3": _as_dnd_time(state.get("dndstart3")),
                    "dndstop3": _as_dnd_time(state.get("dndstop3")),
                    "sirentime": _as_int(state.get("sirentime")),
                    "swmtime": _as_int(state.get("swmtime")),
                },
            ),
            pool_units=merged_units,
        )
        return self._snapshot


def build_history_state_report(history: dict[str, Any], *, device_id: str) -> dict[str, Any]:
    """Build the coordinator report from a BCone history response."""

    return build_state_report(history, device_id=device_id)


def build_state_report(
    history: dict[str, Any],
    *,
    device_id: str,
    mqtt_payloads: tuple[dict[str, Any], ...] = (),
    mqtt_connected: bool = False,
    mqtt_credentials_present: bool = False,
    mqtt_error_type: str | None = None,
) -> dict[str, Any]:
    """Build a coordinator report from REST history plus optional live MQTT state."""

    store = BconeStateStore()
    items = history.get("items") if isinstance(history.get("items"), list) else []
    history_items = sorted((item for item in items if isinstance(item, dict)), key=_history_sort_key)
    for item in history_items:
        store.apply_payload(item)
    for payload in mqtt_payloads:
        store.apply_payload(payload)

    generated_at = datetime.now(UTC)
    rest_history_latest_at = _latest_payload_at(history_items)
    mqtt_latest_at = _latest_payload_at(mqtt_payloads)
    source_payload_at = mqtt_latest_at if mqtt_latest_at is not None else rest_history_latest_at
    entity_state = store.snapshot.as_entity_state()
    final_snapshot = {
        "fields_present": _entity_fields_present(entity_state),
        "pool_unit_count": len(entity_state.get("pool_units") or {}),
        "pool_unit_fields": _snapshot_pool_unit_fields(entity_state),
        "schedule_fields_present": sorted(
            key for key, value in entity_state.get("schedules", {}).items() if value not in (None, "")
        ),
        "private_entity_state": entity_state,
    }
    has_mqtt_payloads = bool(mqtt_payloads)
    return {
        "source": "rest_history+live_mqtt" if has_mqtt_payloads else "rest_history",
        "generated_at_utc": _iso_utc(generated_at),
        "source_payload_at_utc": _iso_utc(source_payload_at),
        "source_payload_age_seconds": _age_seconds(generated_at, source_payload_at),
        "rest_history_latest_at_utc": _iso_utc(rest_history_latest_at),
        "rest_history_age_seconds": _age_seconds(generated_at, rest_history_latest_at),
        "mqtt_latest_at_utc": _iso_utc(mqtt_latest_at),
        "mqtt_payload_age_seconds": _age_seconds(generated_at, mqtt_latest_at),
        "device_id": device_id,
        "mqtt_endpoint": BCONE_MQTT_ENDPOINT,
        "mqtt_port": BCONE_MQTT_PORT,
        "mqtt_topics": [f"bc/{device_id}/ind", f"bc/{device_id}/updatefwstat", "FW"],
        "mqtt_connected": mqtt_connected,
        "mqtt_credentials_present": mqtt_credentials_present,
        "mqtt_error_type": mqtt_error_type,
        "cloud_connected": True,
        "error_type": None,
        "failed_phase": None,
        "history_item_count": len(history_items),
        "mqtt_update_count": len(mqtt_payloads),
        "updates": history_items,
        "safety": {
            "passive_only": True,
            "publishes_requested": False,
            "state_changing": False,
        },
        "final_snapshot": final_snapshot,
    }


def empty_state_report(
    *,
    device_id: str,
    error_type: str | None = None,
    mqtt_connected: bool = False,
    mqtt_credentials_present: bool = False,
    mqtt_error_type: str | None = None,
) -> dict[str, Any]:
    """Build a report when no history state is available."""

    return {
        "source": "rest_history",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "device_id": device_id,
        "mqtt_endpoint": BCONE_MQTT_ENDPOINT,
        "mqtt_port": BCONE_MQTT_PORT,
        "mqtt_topics": [f"bc/{device_id}/ind", f"bc/{device_id}/updatefwstat", "FW"],
        "mqtt_connected": mqtt_connected,
        "mqtt_credentials_present": mqtt_credentials_present,
        "mqtt_error_type": mqtt_error_type,
        "cloud_connected": error_type is None,
        "error_type": error_type,
        "failed_phase": None,
        "history_item_count": 0,
        "mqtt_update_count": 0,
        "updates": [],
        "safety": {
            "passive_only": True,
            "publishes_requested": False,
            "state_changing": False,
        },
        "final_snapshot": {
            "fields_present": [],
            "pool_unit_count": 0,
            "pool_unit_fields": [],
            "schedule_fields_present": [],
            "private_entity_state": {"device_id": device_id, "pool_units": {}},
        },
    }


def _payload_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload)


def _pool_unit_items(state: dict[str, Any], body: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for value in (state.get("pulist"), body.get("pulist")):
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    if isinstance(body.get("pu"), dict):
        candidates.append(body["pu"])
    seen: set[str] = set()
    unique = []
    for item in candidates:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _pool_unit(item: dict[str, Any]) -> PoolUnitState:
    return PoolUnitState(
        puid=_as_str(item.get("puid")),
        serial=_as_str(item.get("sn")),
        name=_as_str(item.get("puname")),
        mac=_as_str(item.get("mac")),
        state=_as_pool_unit_state(item.get("state")),
        sensitivity=_as_sensitivity(item.get("sensitivity")),
        alarms=_as_str(item.get("Alarms") or item.get("alarms")),
        battery=_as_voltage(item.get("PUBatt")),
        battery_state=_as_str(item.get("PUBattState")),
        rssi=_as_int(item.get("PUrssi")),
        temperature=_as_int(item.get("temp")),
        position=_as_str(item.get("Position")),
        light=_as_str(item.get("light")),
        firmware_version=_as_str(item.get("v")),
        firmware_upgrading=_as_bool(item.get("isUpg")),
        keepalive_sent=_as_int(item.get("KASent")),
        keepalive_missed=_as_int(item.get("KAMiss")),
        keepalive_failed=_as_int(item.get("KAFail")),
        last_keepalive_miss_count=_as_int(item.get("LKaMCnt")),
        last_keepalive_fail_count=_as_int(item.get("LKaFCnt")),
        raw=dict(item),
    )


def _pool_unit_diagnostics(unit: PoolUnitState) -> dict[str, int | None]:
    values = {
        "keepalive_sent": unit.keepalive_sent,
        "keepalive_missed": unit.keepalive_missed,
        "keepalive_failed": unit.keepalive_failed,
        "last_keepalive_miss_count": unit.last_keepalive_miss_count,
        "last_keepalive_fail_count": unit.last_keepalive_fail_count,
    }
    return {key: value for key, value in values.items() if value is not None}


def _alarm_active(state: dict[str, Any], body: dict[str, Any], pool_units: tuple[PoolUnitState, ...]) -> bool | None:
    if isinstance(body.get("isAlarm"), bool):
        return body["isAlarm"]
    if isinstance(state.get("alarmReceived"), bool):
        return state["alarmReceived"]
    if any(unit.alarms and unit.alarms not in {"0", "false", "False"} for unit in pool_units):
        return True
    alarm_values = [unit.alarms for unit in pool_units if unit.alarms is not None]
    if alarm_values and all(value in {"0", "false", "False"} for value in alarm_values):
        return False
    return None


def _merge_unit(previous: PoolUnitState | None, current: PoolUnitState) -> PoolUnitState:
    if previous is None:
        return current
    return PoolUnitState(
        puid=current.puid or previous.puid,
        serial=current.serial or previous.serial,
        name=current.name or previous.name,
        mac=current.mac or previous.mac,
        state=current.state or previous.state,
        sensitivity=current.sensitivity if current.sensitivity is not None else previous.sensitivity,
        alarms=current.alarms or previous.alarms,
        battery=current.battery if current.battery is not None else previous.battery,
        battery_state=current.battery_state or previous.battery_state,
        rssi=current.rssi if current.rssi is not None else previous.rssi,
        temperature=current.temperature if current.temperature is not None else previous.temperature,
        position=current.position or previous.position,
        light=current.light or previous.light,
        firmware_version=current.firmware_version or previous.firmware_version,
        firmware_upgrading=current.firmware_upgrading
        if current.firmware_upgrading is not None
        else previous.firmware_upgrading,
        keepalive_sent=current.keepalive_sent if current.keepalive_sent is not None else previous.keepalive_sent,
        keepalive_missed=current.keepalive_missed if current.keepalive_missed is not None else previous.keepalive_missed,
        keepalive_failed=current.keepalive_failed if current.keepalive_failed is not None else previous.keepalive_failed,
        last_keepalive_miss_count=current.last_keepalive_miss_count
        if current.last_keepalive_miss_count is not None
        else previous.last_keepalive_miss_count,
        last_keepalive_fail_count=current.last_keepalive_fail_count
        if current.last_keepalive_fail_count is not None
        else previous.last_keepalive_fail_count,
        raw={**previous.raw, **current.raw},
    )


def _merge_non_none(previous: dict[str, str | None], current: dict[str, str | None]) -> dict[str, str | None]:
    merged = dict(previous)
    for key, value in current.items():
        if value is not None:
            merged[key] = value
    return merged


def _history_sort_key(item: dict[str, Any]) -> tuple[float, str]:
    time_value = _as_int(item.get("time"))
    if time_value is not None:
        return (float(time_value), "")
    for key in ("createdAt", "updatedAt"):
        value = item.get(key)
        if isinstance(value, str):
            try:
                return (datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp(), value)
            except ValueError:
                pass
    return (0, "")


def _latest_payload_at(payloads: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> datetime | None:
    timestamps = [timestamp for payload in payloads if (timestamp := _payload_at(payload)) is not None]
    return max(timestamps) if timestamps else None


def _payload_at(payload: dict[str, Any]) -> datetime | None:
    body = _payload_dict(payload)
    state = body.get("data") if isinstance(body.get("data"), dict) else body
    for source, key in ((body, "createdAt"), (body, "updatedAt"), (state, "timestamp"), (body, "time")):
        value = source.get(key)
        parsed = _as_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.isdigit():
            return _as_datetime(int(text))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _age_seconds(now: datetime, value: datetime | None) -> int | None:
    if value is None:
        return None
    return max(0, int((now - value).total_seconds()))


def _entity_fields_present(entity_state: dict[str, Any]) -> list[str]:
    return sorted(
        key
        for key, value in entity_state.items()
        if key != "pool_units" and value not in (None, [], {}, ())
    )


def _snapshot_pool_unit_fields(entity_state: dict[str, Any]) -> list[str]:
    fields: set[str] = set()
    pool_units = entity_state.get("pool_units")
    if isinstance(pool_units, dict):
        for unit in pool_units.values():
            if isinstance(unit, dict):
                fields.update(key for key, value in unit.items() if value is not None)
    return sorted(fields)


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_dnd_time(value: Any) -> str | None:
    converted = _as_minutes_since_midnight(value)
    if converted is not None:
        return converted
    if _as_int(value) == 2000:
        return "00:00"
    return _as_str(value) if value is not None else None


def _as_hub_clock(value: Any) -> str | None:
    converted = _as_minutes_since_midnight(value)
    if converted is not None:
        return converted
    return _as_str(value) if value is not None else None


def _as_minutes_since_midnight(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and ":" in value:
        parts = value.strip().split(":", maxsplit=1)
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return value
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return None

    minutes = _as_int(value)
    if minutes is None:
        return None
    if 0 <= minutes < 24 * 60:
        hour, minute = divmod(minutes, 60)
        return f"{hour:02d}:{minute:02d}"
    return None


def _as_voltage(value: Any) -> float | None:
    millivolts = _as_int(value)
    if millivolts is None:
        return None
    return round(millivolts / 1000, 3)


def _as_sensitivity(value: Any) -> float | None:
    raw = _as_int(value)
    if raw is None:
        return None
    return round((raw - 9) / 2, 1)


def _as_pool_unit_state(value: Any) -> str | None:
    raw = _as_str(value)
    if raw is None:
        return None
    return {
        "1": "On/Armed",
        "2": "Off/Disarmed",
        "3": "Swim Mode",
    }.get(raw, raw)


def _as_bool(value: Any) -> bool | None:
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


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None
