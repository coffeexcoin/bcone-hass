from __future__ import annotations

from custom_components.bcone.state import build_history_state_report


def test_history_report_decodes_hub_and_pool_unit_state() -> None:
    report = build_history_state_report(
        {
            "items": [
                {
                    "time": 100,
                    "data": {
                        "DeviceID": "device-123",
                        "sn": "hub-serial",
                        "timestamp": "1782864490350",
                        "sysname": "Pool",
                        "hubatt": "91",
                        "chst": "dock",
                        "isUpg": "0",
                        "v": "V3.4.5",
                        "src": "1",
                        "top3": "ind",
                        "time": "1208",
                        "gmtof": "-240",
                        "dndstart": "1200",
                        "dndstop": "360",
                        "dndstart2": "2000",
                        "dndstop2": "2000",
                        "dndstart3": "00:00",
                        "dndstop3": "00:00",
                        "HUrssi": "-64",
                        "WifiRssi": "-58",
                        "pulist": [
                            {
                                "puid": "1",
                                "sn": "pool-serial-1",
                                "puname": "Unit A",
                                "state": "2",
                                "sensitivity": "19",
                                "PUBatt": "88",
                                "PUBattState": "ok",
                                "PUrssi": "-54",
                                "temp": "72",
                                "Position": "center",
                                "light": "1",
                                "v": "V3.0.10",
                                "KASent": "13",
                                "KAMiss": "0",
                                "KAFail": "0",
                            }
                        ],
                    },
                    "isAlarm": False,
                }
            ],
            "success": True,
        },
        device_id="device-123",
    )

    state = report["final_snapshot"]["private_entity_state"]
    assert report["source"] == "rest_history"
    assert report["cloud_connected"] is True
    assert report["mqtt_connected"] is False
    assert report["mqtt_topics"] == ["bc/device-123/ind", "bc/device-123/updatefwstat", "FW"]
    assert state["device_id"] == "device-123"
    assert state["system_name"] == "Pool"
    assert state["alarm_active"] is False
    assert state["hub_battery"] == 91
    assert state["charging_state"] == "dock"
    assert state["hub_rssi"] == -64
    assert state["wifi_rssi"] == -58
    assert state["schedules"]["dndstart"] == "20:00"
    assert state["schedules"]["dndstop"] == "06:00"
    assert state["schedules"]["dndstart2"] == "00:00"
    assert state["schedules"]["dndstop2"] == "00:00"
    assert state["schedules"]["dndstart3"] == "00:00"
    assert state["schedules"]["dndstop3"] == "00:00"
    assert state["primary_pool_unit_state"] == "2"
    assert state["pool_units"]["1"]["name"] == "Unit A"
    assert state["pool_units"]["1"]["sensitivity"] == 19
    assert state["pool_units"]["1"]["battery"] == 88
    assert state["pool_units"]["1"]["rssi"] == -54
    assert "raw" not in state["pool_units"]["1"]
