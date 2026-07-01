from __future__ import annotations

from custom_components.bcone.state import build_history_state_report, build_state_report


def test_history_report_decodes_hub_and_pool_unit_state() -> None:
    report = build_history_state_report(
        {
            "items": [
                {
                    "createdAt": "2026-07-01T19:49:35.667Z",
                    "time": 100,
                    "data": {
                        "DeviceID": "device-123",
                        "sn": "hub-serial",
                        "timestamp": "1782864490350",
                        "sysname": "Pool",
                        "hubatt": "4121",
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
                        "sirentime": "180",
                        "swmtime": "10",
                        "HUrssi": "-64",
                        "WifiRssi": "-58",
                        "pulist": [
                            {
                                "puid": "1",
                                "sn": "pool-serial-1",
                                "puname": "Unit A",
                                "state": "2",
                                "sensitivity": "19",
                                "PUBatt": "2858",
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
    assert report["source_payload_at_utc"] == "2026-07-01T19:49:35.667000Z"
    assert report["rest_history_latest_at_utc"] == "2026-07-01T19:49:35.667000Z"
    assert report["mqtt_latest_at_utc"] is None
    assert isinstance(report["rest_history_age_seconds"], int)
    assert report["cloud_connected"] is True
    assert report["mqtt_connected"] is False
    assert report["mqtt_topics"] == ["bc/device-123/ind", "bc/device-123/updatefwstat", "FW"]
    assert state["device_id"] == "device-123"
    assert state["system_name"] == "Pool"
    assert state["alarm_active"] is False
    assert state["hub_battery"] == 4.121
    assert state["charging_state"] == "dock"
    assert state["hub_clock"] == "20:08"
    assert state["hub_rssi"] == -64
    assert state["wifi_rssi"] == -58
    assert state["schedules"]["dndstart"] == "20:00"
    assert state["schedules"]["dndstop"] == "06:00"
    assert state["schedules"]["dndstart2"] == "00:00"
    assert state["schedules"]["dndstop2"] == "00:00"
    assert state["schedules"]["dndstart3"] == "00:00"
    assert state["schedules"]["dndstop3"] == "00:00"
    assert state["schedules"]["sirentime"] == 180
    assert state["schedules"]["swmtime"] == 10
    assert state["primary_pool_unit_state"] == "Off/Disarmed"
    assert state["pool_units"]["1"]["name"] == "Unit A"
    assert state["pool_units"]["1"]["state"] == "Off/Disarmed"
    assert state["pool_units"]["1"]["sensitivity"] == 5.0
    assert state["pool_units"]["1"]["battery"] == 2.858
    assert state["pool_units"]["1"]["rssi"] == -54
    assert state["pool_units"]["1"]["temperature"] == 72
    assert "raw" not in state["pool_units"]["1"]


def test_live_mqtt_payload_overrides_stale_rest_names() -> None:
    report = build_state_report(
        {
            "items": [
                {
                    "createdAt": "2026-07-01T19:49:35.667Z",
                    "time": 100,
                    "data": {
                        "DeviceID": "device-123",
                        "sysname": "BCONE",
                        "pulist": [
                            {"puid": "0", "puname": "POOL", "PUBatt": "2858", "sensitivity": "19", "state": "2"}
                        ],
                    },
                }
            ]
        },
        device_id="device-123",
        mqtt_payloads=(
            {
                "timestamp": "1782936225000",
                "sysname": "BCone Hub",
                "pulist": [{"puid": "0", "puname": "Pool", "PUBatt": "2859", "sensitivity": "12", "state": "3"}],
            },
        ),
        mqtt_connected=True,
        mqtt_credentials_present=True,
    )

    state = report["final_snapshot"]["private_entity_state"]
    assert report["source"] == "rest_history+live_mqtt"
    assert report["rest_history_latest_at_utc"] == "2026-07-01T19:49:35.667000Z"
    assert report["mqtt_latest_at_utc"] == "2026-07-01T20:03:45Z"
    assert report["source_payload_at_utc"] == "2026-07-01T20:03:45Z"
    assert report["mqtt_connected"] is True
    assert report["mqtt_credentials_present"] is True
    assert report["mqtt_update_count"] == 1
    assert state["system_name"] == "BCone Hub"
    assert state["pool_units"]["0"]["name"] == "Pool"
    assert state["pool_units"]["0"]["state"] == "Swim Mode"
    assert state["pool_units"]["0"]["sensitivity"] == 1.5
    assert state["pool_units"]["0"]["battery"] == 2.859
