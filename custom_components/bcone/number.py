"""BCone number entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .control import MAX_SENSITIVITY, MIN_SENSITIVITY, SENSITIVITY_STEP
from .entity_plan import device_info_from_report, pool_unit_ids, value_from_report


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up BCone numbers."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    known_pool_unit_ids: set[str] = set()

    def add_pool_unit_entities() -> None:
        new_ids = [unit_id for unit_id in pool_unit_ids(coordinator.data) if unit_id not in known_pool_unit_ids]
        if not new_ids:
            return
        known_pool_unit_ids.update(new_ids)
        async_add_entities(BconeSensitivityNumber(coordinator, entry.entry_id, unit_id) for unit_id in new_ids)

    add_pool_unit_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_pool_unit_entities))


class BconeSensitivityNumber(CoordinatorEntity, NumberEntity):
    """Number entity for pool-unit sensitivity."""

    _attr_name = "Sensitivity"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = MIN_SENSITIVITY
    _attr_native_max_value = MAX_SENSITIVITY
    _attr_native_step = SENSITIVITY_STEP

    def __init__(self, coordinator: Any, entry_id: str, pool_unit_id: str) -> None:
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.pool_unit_id = pool_unit_id
        self._attr_unique_id = f"{entry_id}_pool_{pool_unit_id}_sensitivity_number"

    @property
    def native_value(self) -> float | None:
        value = value_from_report(
            self.coordinator.data,
            "state.pool_units[*].sensitivity",
            pool_unit_id=self.pool_unit_id,
        )
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    @property
    def available(self) -> bool:
        return bool(self.native_value is not None and self.coordinator.can_write_sensitivity(self.pool_unit_id))

    @property
    def device_info(self) -> dict[str, Any]:
        return device_info_from_report(
            self.coordinator.data,
            entry_id=self.entry_id,
            domain=DOMAIN,
            pool_unit_id=self.pool_unit_id,
        )

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_sensitivity(self.pool_unit_id, value)
