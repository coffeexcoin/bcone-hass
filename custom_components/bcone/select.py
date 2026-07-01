"""BCone select entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .control import POOL_UNIT_STATE_OPTIONS
from .entity_plan import device_info_from_report, pool_unit_ids, value_from_report


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up BCone selects."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    known_pool_unit_ids: set[str] = set()

    def add_pool_unit_entities() -> None:
        new_ids = [unit_id for unit_id in pool_unit_ids(coordinator.data) if unit_id not in known_pool_unit_ids]
        if not new_ids:
            return
        known_pool_unit_ids.update(new_ids)
        async_add_entities(BconePoolUnitStateSelect(coordinator, entry.entry_id, unit_id) for unit_id in new_ids)

    add_pool_unit_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_pool_unit_entities))


class BconePoolUnitStateSelect(CoordinatorEntity, SelectEntity):
    """Select for pool-unit mode/state."""

    _attr_name = "State"
    _attr_has_entity_name = True
    _attr_options = list(POOL_UNIT_STATE_OPTIONS)

    def __init__(self, coordinator: Any, entry_id: str, pool_unit_id: str) -> None:
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.pool_unit_id = pool_unit_id
        self._attr_unique_id = f"{entry_id}_pool_{pool_unit_id}_state_select"

    @property
    def current_option(self) -> str | None:
        value = value_from_report(
            self.coordinator.data,
            "state.pool_units[*].state",
            pool_unit_id=self.pool_unit_id,
        )
        return value if value in POOL_UNIT_STATE_OPTIONS else None

    @property
    def available(self) -> bool:
        return bool(self.coordinator.mqtt_writes_available and self.current_option is not None)

    @property
    def device_info(self) -> dict[str, Any]:
        return device_info_from_report(
            self.coordinator.data,
            entry_id=self.entry_id,
            domain=DOMAIN,
            pool_unit_id=self.pool_unit_id,
        )

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_pool_unit_state(self.pool_unit_id, option)
