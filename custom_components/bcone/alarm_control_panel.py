"""BCone alarm control panel entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .control import POOL_UNIT_STATE_OPTIONS
from .entity_plan import device_info_from_report, pool_unit_ids, value_from_report

BCONE_TO_ALARM_STATE = {
    "On/Armed": AlarmControlPanelState.ARMED_AWAY,
    "Off/Disarmed": AlarmControlPanelState.DISARMED,
    "Swim Mode": AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up BCone alarm control panels."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    known_pool_unit_ids: set[str] = set()

    def add_pool_unit_entities() -> None:
        new_ids = [unit_id for unit_id in pool_unit_ids(coordinator.data) if unit_id not in known_pool_unit_ids]
        if not new_ids:
            return
        known_pool_unit_ids.update(new_ids)
        async_add_entities(BconePoolUnitAlarmControlPanel(coordinator, entry.entry_id, unit_id) for unit_id in new_ids)

    add_pool_unit_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_pool_unit_entities))


class BconePoolUnitAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Alarm panel for one BCone floating pool unit."""

    _attr_name = "Alarm"
    _attr_has_entity_name = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
    )

    def __init__(self, coordinator: Any, entry_id: str, pool_unit_id: str) -> None:
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.pool_unit_id = pool_unit_id
        self._attr_unique_id = f"{entry_id}_pool_{pool_unit_id}_alarm_control_panel"

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        alarms = value_from_report(
            self.coordinator.data,
            "state.pool_units[*].alarms",
            pool_unit_id=self.pool_unit_id,
        )
        if _alarm_active(alarms):
            return AlarmControlPanelState.TRIGGERED

        mode = self._pool_unit_mode()
        return BCONE_TO_ALARM_STATE.get(mode)

    @property
    def available(self) -> bool:
        return bool(self._pool_unit_mode() in POOL_UNIT_STATE_OPTIONS)

    @property
    def device_info(self) -> dict[str, Any]:
        return device_info_from_report(
            self.coordinator.data,
            entry_id=self.entry_id,
            domain=DOMAIN,
            pool_unit_id=self.pool_unit_id,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mode = self._pool_unit_mode()
        return {"bcone_mode": mode} if mode else {}

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self.coordinator.async_set_pool_unit_state(self.pool_unit_id, "Off/Disarmed")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self.coordinator.async_set_pool_unit_state(self.pool_unit_id, "On/Armed")

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        await self.coordinator.async_set_pool_unit_state(self.pool_unit_id, "Swim Mode")

    def _pool_unit_mode(self) -> str | None:
        value = value_from_report(
            self.coordinator.data,
            "state.pool_units[*].state",
            pool_unit_id=self.pool_unit_id,
        )
        return value if value in POOL_UNIT_STATE_OPTIONS else None


def _alarm_active(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered not in {"", "0", "false", "none", "off"}
    return False
