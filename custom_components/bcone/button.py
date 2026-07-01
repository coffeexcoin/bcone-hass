"""BCone button entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity_plan import device_info_from_report


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up BCone buttons."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BconeStopSirenButton(coordinator, entry.entry_id)])


class BconeStopSirenButton(CoordinatorEntity, ButtonEntity):
    """Button that stops the active BCone siren."""

    _attr_name = "Stop Siren"

    def __init__(self, coordinator: Any, entry_id: str) -> None:
        super().__init__(coordinator)
        self.entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_stop_siren"

    @property
    def available(self) -> bool:
        return bool(self.coordinator.mqtt_writes_available)

    @property
    def device_info(self) -> dict[str, Any]:
        return device_info_from_report(self.coordinator.data, entry_id=self.entry_id, domain=DOMAIN)

    async def async_press(self) -> None:
        await self.coordinator.async_stop_siren()
