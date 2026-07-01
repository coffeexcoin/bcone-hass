from __future__ import annotations

import pytest

from custom_components.bcone.control import (
    encode_sensitivity,
    pool_unit_state_command,
    sensitivity_command,
    stop_siren_command,
)


def test_pool_unit_state_command_uses_observed_topic_and_payload_shape() -> None:
    command = pool_unit_state_command("device-123", "0", "Swim Mode")

    assert command.topic == "bc/device-123/req/pu/state"
    assert command.payload == {"puid": "0", "val": "3"}


def test_stop_siren_command_uses_empty_payload() -> None:
    command = stop_siren_command("device-123")

    assert command.topic == "bc/device-123/req/stopsiren"
    assert command.payload == {}


def test_sensitivity_command_uses_raw_app_scale() -> None:
    command = sensitivity_command("device-123", "0", 1.5)

    assert command.topic == "bc/device-123/req/pu/sensitivity"
    assert command.payload == {"puid": "0", "sensitivity": "12"}


def test_encode_sensitivity_allows_half_steps_from_one_to_five() -> None:
    assert encode_sensitivity(1.0) == 11
    assert encode_sensitivity(1.5) == 12
    assert encode_sensitivity(5.0) == 19


@pytest.mark.parametrize("value", [0.5, 1.25, 5.5])
def test_encode_sensitivity_rejects_unknown_values(value: float) -> None:
    with pytest.raises(ValueError):
        encode_sensitivity(value)
