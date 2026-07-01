"""Read-only BCone sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity_plan import (
    device_info_from_report,
    entities_for_platform,
    entity_available,
    timestamp_from_report,
    unseen_pool_unit_ids,
    value_from_report,
)


@dataclass(frozen=True, kw_only=True)
class BconeSensorDescription(SensorEntityDescription):
    """Description for a read-only BCone sensor."""

    source_path: str
    scope: str
    per_pool_unit: bool = False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up BCone sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = await hass.async_add_executor_job(entities_for_platform, "sensor")
    descriptions = tuple(_sensor_description(entity) for entity in entities)
    fixed_descriptions = [description for description in descriptions if not description.per_pool_unit]
    pool_descriptions = [description for description in descriptions if description.per_pool_unit]
    known_pool_unit_ids: set[str] = set()

    async_add_entities(BconeSensor(coordinator, entry.entry_id, description) for description in fixed_descriptions)

    def add_pool_unit_entities() -> None:
        new_ids = unseen_pool_unit_ids(coordinator.data, known_pool_unit_ids)
        if not new_ids:
            return
        known_pool_unit_ids.update(new_ids)
        async_add_entities(
            BconeSensor(coordinator, entry.entry_id, description, pool_unit_id=unit_id)
            for unit_id in new_ids
            for description in pool_descriptions
        )

    add_pool_unit_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_pool_unit_entities))


class BconeSensor(CoordinatorEntity, SensorEntity):
    """BCone read-only sensor."""

    entity_description: BconeSensorDescription

    def __init__(
        self,
        coordinator: Any,
        entry_id: str,
        description: BconeSensorDescription,
        pool_unit_id: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.entry_id = entry_id
        self.pool_unit_id = pool_unit_id
        key_parts = [entry_id]
        if pool_unit_id is not None:
            key_parts.append(f"pool_{pool_unit_id}")
            self._attr_name = f"Pool Unit {pool_unit_id} {description.name}"
        key_parts.append(description.key)
        self._attr_unique_id = "_".join(key_parts)

    @property
    def native_value(self) -> Any:
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            return timestamp_from_report(self.coordinator.data, self.entity_description.source_path)
        return value_from_report(
            self.coordinator.data,
            self.entity_description.source_path,
            pool_unit_id=self.pool_unit_id,
        )

    @property
    def available(self) -> bool:
        return entity_available(
            self.coordinator.data,
            self.entity_description.scope,
            self.entity_description.source_path,
            pool_unit_id=self.pool_unit_id,
        )

    @property
    def device_info(self) -> dict[str, Any]:
        return device_info_from_report(
            self.coordinator.data,
            entry_id=self.entry_id,
            domain=DOMAIN,
            pool_unit_id=self.pool_unit_id,
        )


def _sensor_description(entity: dict[str, Any]) -> BconeSensorDescription:
    return BconeSensorDescription(
        key=str(entity["entity_key"]),
        name=str(entity["name"]),
        source_path=str(entity["source_path"]),
        scope=str(entity["scope"]),
        per_pool_unit=bool(entity.get("per_pool_unit")),
        entity_category=_entity_category(entity),
        device_class=_sensor_device_class(entity),
        native_unit_of_measurement=entity.get("native_unit_of_measurement"),
    )


def _entity_category(entity: dict[str, Any]) -> EntityCategory | None:
    return EntityCategory.DIAGNOSTIC if entity.get("category") == "diagnostic" else None


def _sensor_device_class(entity: dict[str, Any]) -> SensorDeviceClass | str | None:
    if entity.get("device_class") == "signal_strength":
        return SensorDeviceClass.SIGNAL_STRENGTH
    if entity.get("device_class") == "timestamp":
        return SensorDeviceClass.TIMESTAMP
    if entity.get("device_class") == "voltage":
        return SensorDeviceClass.VOLTAGE
    return entity.get("device_class")
