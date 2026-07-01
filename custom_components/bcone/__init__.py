"""BCone read-only Home Assistant integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BconeApiClient, BconeApiError, BconeTokens
from .const import CONF_DEVICE_ID, CONF_EMAIL, CONF_TOKENS, DOMAIN, PLATFORMS
from .mqtt import BconeMqttCredentials, BconeMqttListener
from .state import build_state_report, empty_state_report

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BCone read-only monitoring from a config entry."""

    coordinator = BconeReadonlyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start_mqtt()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a BCone config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if isinstance(coordinator, BconeReadonlyCoordinator):
            await coordinator.async_stop_mqtt()
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


class BconeReadonlyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll BCone read-only cloud state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=2),
        )
        self.entry = entry
        self.api = BconeApiClient(async_get_clientsession(hass))
        self._last_history: dict[str, Any] = {}
        self._mqtt_payloads: list[dict[str, Any]] = []
        self._mqtt_credentials = BconeMqttCredentials.from_hass(hass)
        self._mqtt_listener: BconeMqttListener | None = None
        self._mqtt_connected = False
        self._mqtt_error_type: str | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        device_id = str(self.entry.data[CONF_DEVICE_ID])
        try:
            await self._valid_tokens()
            history = await self.api.get_device_history(device_id)
            self._last_history = history
            if self._mqtt_listener is None and self._mqtt_credentials.available:
                self.async_start_mqtt()
            return self._build_report()
        except (BconeApiError, ClientResponseError) as exc:
            raise UpdateFailed(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - coordinator should surface unexpected failures.
            raise UpdateFailed(str(exc)) from exc

    def async_start_mqtt(self) -> None:
        """Start optional MQTT live-state monitoring when credentials exist."""

        if self._mqtt_listener is not None:
            return
        if not self._mqtt_credentials.available:
            self._mqtt_connected = False
            self._mqtt_error_type = None
            return

        device_id = str(self.entry.data[CONF_DEVICE_ID])
        self._mqtt_listener = BconeMqttListener(
            self.hass,
            device_id=device_id,
            credentials=self._mqtt_credentials,
            status_callback=self._handle_mqtt_status,
            payload_callback=self._handle_mqtt_payload,
        )
        self._mqtt_listener.start()

    async def async_stop_mqtt(self) -> None:
        """Stop optional MQTT live-state monitoring."""

        if self._mqtt_listener is not None:
            await self._mqtt_listener.stop()
            self._mqtt_listener = None

    def _handle_mqtt_status(self, connected: bool, error_type: str | None) -> None:
        self._mqtt_connected = connected
        self._mqtt_error_type = error_type
        self._push_current_report()

    def _handle_mqtt_payload(self, payload: dict[str, Any]) -> None:
        self._mqtt_connected = True
        self._mqtt_error_type = None
        self._mqtt_payloads.append(payload)
        self._mqtt_payloads = self._mqtt_payloads[-10:]
        self._sync_device_registry_names()
        self._push_current_report()

    def _push_current_report(self) -> None:
        if self.data is not None:
            self.async_set_updated_data(self._build_report())

    def _build_report(self) -> dict[str, Any]:
        return build_state_report(
            self._last_history,
            device_id=str(self.entry.data[CONF_DEVICE_ID]),
            mqtt_payloads=tuple(self._mqtt_payloads),
            mqtt_connected=self._mqtt_connected,
            mqtt_credentials_present=self._mqtt_credentials.available,
            mqtt_error_type=self._mqtt_error_type,
        )

    def _sync_device_registry_names(self) -> None:
        """Update registered device names from live MQTT state when HA has no user override."""

        report = self._build_report()
        snapshot = report.get("final_snapshot") if isinstance(report.get("final_snapshot"), dict) else {}
        state = snapshot.get("private_entity_state") if isinstance(snapshot.get("private_entity_state"), dict) else {}
        device_id = state.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            return

        registry = dr.async_get(self.hass)
        hub_name = state.get("system_name")
        if isinstance(hub_name, str) and hub_name.strip():
            self._update_device_name(registry, identifier=device_id, name=hub_name.strip())

        units = state.get("pool_units")
        if not isinstance(units, dict):
            return
        for pool_unit_id, unit in units.items():
            if not isinstance(unit, dict):
                continue
            unit_name = unit.get("name")
            if isinstance(unit_name, str) and unit_name.strip():
                self._update_device_name(
                    registry,
                    identifier=f"{device_id}:pool_unit:{pool_unit_id}",
                    name=unit_name.strip(),
                )

    def _update_device_name(self, registry: dr.DeviceRegistry, *, identifier: str, name: str) -> None:
        device = registry.async_get_device(identifiers={(DOMAIN, identifier)})
        if device is None or device.name_by_user or device.name == name:
            return
        registry.async_update_device(device.id, name=name)

    async def _valid_tokens(self) -> BconeTokens:
        tokens = BconeTokens.from_dict(self.entry.data[CONF_TOKENS])
        if not tokens.expired:
            return tokens

        refreshed = await self.api.refresh(tokens, username=str(self.entry.data.get(CONF_EMAIL) or ""))
        data = dict(self.entry.data)
        data[CONF_TOKENS] = refreshed.as_dict()
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        return refreshed


def initial_report(entry: ConfigEntry) -> dict[str, Any]:
    """Return a minimal redacted report for diagnostics before first refresh."""

    return empty_state_report(device_id=str(entry.data.get(CONF_DEVICE_ID) or "unknown"))
