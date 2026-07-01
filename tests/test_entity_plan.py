from __future__ import annotations

from custom_components.bcone.entity_plan import entities_for_platform, device_info_from_report


def test_battery_voltage_entities_are_diagnostic_voltage_sensors() -> None:
    entities = {entity["entity_key"]: entity for entity in entities_for_platform("sensor")}

    assert entities["hub_battery_raw"]["category"] == "diagnostic"
    assert entities["hub_battery_raw"]["device_class"] == "voltage"
    assert entities["hub_battery_raw"]["name"] == "Hub Battery Voltage"
    assert entities["hub_battery_raw"]["native_unit_of_measurement"] == "V"
    assert entities["hub_battery_raw"]["suggested_display_precision"] == 3

    assert entities["pool_unit_battery_raw"]["category"] == "diagnostic"
    assert entities["pool_unit_battery_raw"]["device_class"] == "voltage"
    assert entities["pool_unit_battery_raw"]["name"] == "Battery Voltage"
    assert entities["pool_unit_battery_raw"]["native_unit_of_measurement"] == "V"
    assert entities["pool_unit_battery_raw"]["suggested_display_precision"] == 3


def test_battery_state_entities_remain_diagnostic_state_sensors() -> None:
    entities = {entity["entity_key"]: entity for entity in entities_for_platform("sensor")}

    assert entities["hub_battery_state"]["category"] == "diagnostic"
    assert entities["hub_battery_state"]["name"] == "Hub Battery State"
    assert "device_class" not in entities["hub_battery_state"]

    assert entities["pool_unit_battery_state"]["category"] == "diagnostic"
    assert entities["pool_unit_battery_state"]["name"] == "Battery State"
    assert "device_class" not in entities["pool_unit_battery_state"]


def test_battery_problem_entities_are_diagnostic_battery_binary_sensors() -> None:
    entities = {entity["entity_key"]: entity for entity in entities_for_platform("binary_sensor")}

    assert entities["hub_battery_problem"]["category"] == "diagnostic"
    assert entities["hub_battery_problem"]["device_class"] == "battery"
    assert entities["hub_battery_problem"]["name"] == "Hub Battery State"
    assert entities["hub_battery_problem"]["source_path"] == "state.hub_battery_problem"

    assert entities["pool_unit_battery_problem"]["category"] == "diagnostic"
    assert entities["pool_unit_battery_problem"]["device_class"] == "battery"
    assert entities["pool_unit_battery_problem"]["name"] == "Battery State"
    assert entities["pool_unit_battery_problem"]["source_path"] == "state.pool_units[*].battery_problem"


def test_stale_freshness_diagnostics_are_not_exposed_as_entities() -> None:
    entities = {entity["entity_key"] for entity in entities_for_platform("sensor")}

    assert "source_payload_at_utc" not in entities
    assert "source_payload_age_seconds" not in entities
    assert "rest_history_latest_at_utc" not in entities
    assert "rest_history_age_seconds" not in entities
    assert "mqtt_latest_at_utc" not in entities
    assert "mqtt_payload_age_seconds" not in entities


def test_mqtt_error_type_is_exposed_as_monitor_diagnostic() -> None:
    entities = {entity["entity_key"]: entity for entity in entities_for_platform("sensor")}

    assert entities["mqtt_error_type"]["category"] == "diagnostic"
    assert entities["mqtt_error_type"]["name"] == "MQTT Error Type"
    assert entities["mqtt_error_type"]["scope"] == "monitor"
    assert entities["mqtt_error_type"]["source_path"] == "report.mqtt_error_type"


def test_hub_device_info_uses_system_name() -> None:
    report = {
        "final_snapshot": {
            "private_entity_state": {
                "device_id": "hub-123",
                "system_name": "BCONE",
            }
        }
    }

    info = device_info_from_report(report, entry_id="entry-123", domain="bcone")

    assert info["identifiers"] == {("bcone", "hub-123")}
    assert info["name"] == "BCONE"


def test_pool_unit_device_info_uses_pool_unit_name() -> None:
    report = {
        "final_snapshot": {
            "private_entity_state": {
                "device_id": "hub-123",
                "pool_units": {
                    "0": {
                        "name": "POOL",
                        "serial": "pool-serial-0",
                        "firmware_version": "V1.2.3",
                    }
                },
            }
        }
    }

    info = device_info_from_report(report, entry_id="entry-123", domain="bcone", pool_unit_id="0")

    assert info["identifiers"] == {("bcone", "hub-123:pool_unit:0")}
    assert info["name"] == "POOL"
    assert info["via_device"] == ("bcone", "hub-123")
    assert info["serial_number"] == "pool-serial-0"
    assert info["sw_version"] == "V1.2.3"


def test_pool_unit_device_info_falls_back_to_pool_unit_id() -> None:
    report = {
        "final_snapshot": {
            "private_entity_state": {
                "device_id": "hub-123",
                "pool_units": {"0": {"name": ""}},
            }
        }
    }

    info = device_info_from_report(report, entry_id="entry-123", domain="bcone", pool_unit_id="0")

    assert info["name"] == "Pool Unit 0"
