from __future__ import annotations

from custom_components.bcone.entity_plan import device_info_from_report


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
