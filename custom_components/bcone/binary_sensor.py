"""Read-only BCone binary sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity_plan import bool_from_report, device_info_from_report, entities_for_platform, entity_available, unseen_pool_unit_ids


@dataclass(frozen=True, kw_only=True)
class BconeBinarySensorDescription(BinarySensorEntityDescription):
    """Description for a read-only BCone binary sensor."""

    source_path: str
    scope: str
    per_pool_unit: bool = False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up BCone binary sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = await hass.async_add_executor_job(entities_for_platform, "binary_sensor")
    descriptions = tuple(_binary_sensor_description(entity) for entity in entities)
    fixed_descriptions = [description for description in descriptions if not description.per_pool_unit]
    pool_descriptions = [description for description in descriptions if description.per_pool_unit]
    known_pool_unit_ids: set[str] = set()

    async_add_entities(BconeBinarySensor(coordinator, entry.entry_id, description) for description in fixed_descriptions)

    def add_pool_unit_entities() -> None:
        new_ids = unseen_pool_unit_ids(coordinator.data, known_pool_unit_ids)
        if not new_ids:
            return
        known_pool_unit_ids.update(new_ids)
        async_add_entities(
            BconeBinarySensor(coordinator, entry.entry_id, description, pool_unit_id=unit_id)
            for unit_id in new_ids
            for description in pool_descriptions
        )

    add_pool_unit_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_pool_unit_entities))


class BconeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """BCone read-only binary sensor."""

    entity_description: BconeBinarySensorDescription

    def __init__(
        self,
        coordinator: Any,
        entry_id: str,
        description: BconeBinarySensorDescription,
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
    def is_on(self) -> bool | None:
        return bool_from_report(
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


def _binary_sensor_description(entity: dict[str, Any]) -> BconeBinarySensorDescription:
    return BconeBinarySensorDescription(
        key=str(entity["entity_key"]),
        name=str(entity["name"]),
        source_path=str(entity["source_path"]),
        scope=str(entity["scope"]),
        per_pool_unit=bool(entity.get("per_pool_unit")),
        entity_category=_entity_category(entity),
        device_class=_binary_device_class(entity),
    )


def _entity_category(entity: dict[str, Any]) -> EntityCategory | None:
    return EntityCategory.DIAGNOSTIC if entity.get("category") == "diagnostic" else None


def _binary_device_class(entity: dict[str, Any]) -> BinarySensorDeviceClass | str | None:
    if entity.get("device_class") == "connectivity":
        return BinarySensorDeviceClass.CONNECTIVITY
    if entity.get("device_class") == "problem":
        return BinarySensorDeviceClass.PROBLEM
    return entity.get("device_class")
