"""BCone state-changing command builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

POOL_UNIT_STATE_OPTIONS = ("On/Armed", "Off/Disarmed", "Swim Mode")
POOL_UNIT_STATE_CODES = {
    "On/Armed": "1",
    "Off/Disarmed": "2",
    "Swim Mode": "3",
}

MIN_SENSITIVITY = 1.0
MAX_SENSITIVITY = 5.0
SENSITIVITY_STEP = 0.5


@dataclass(frozen=True, slots=True)
class MqttCommand:
    """Validated BCone MQTT command."""

    topic: str
    payload: dict[str, Any]


def pool_unit_state_command(device_id: str, pool_unit_id: str, option: str) -> MqttCommand:
    """Build a pool-unit mode command."""

    try:
        code = POOL_UNIT_STATE_CODES[option]
    except KeyError as exc:
        raise ValueError(f"unsupported pool unit state: {option}") from exc
    return MqttCommand(
        topic=f"bc/{device_id}/req/pu/state",
        payload={"puid": str(pool_unit_id), "val": code},
    )


def stop_siren_command(device_id: str) -> MqttCommand:
    """Build a stop-siren command."""

    return MqttCommand(topic=f"bc/{device_id}/req/stopsiren", payload={})


def sensitivity_command(device_id: str, pool_unit_id: str, value: float) -> MqttCommand:
    """Build a pool-unit sensitivity command."""

    return MqttCommand(
        topic=f"bc/{device_id}/req/pu/sensitivity",
        payload={"puid": str(pool_unit_id), "sensitivity": str(encode_sensitivity(value))},
    )


def encode_sensitivity(value: float) -> int:
    """Return the raw BCone sensitivity value for the app's 1.0-5.0 scale."""

    rounded = round(value * 2) / 2
    if rounded != value or rounded < MIN_SENSITIVITY or rounded > MAX_SENSITIVITY:
        raise ValueError("sensitivity must be from 1.0 to 5.0 in 0.5 increments")
    return int(round(rounded * 2 + 9))
