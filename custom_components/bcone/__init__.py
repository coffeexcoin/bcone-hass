"""BCone read-only Home Assistant integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BconeApiClient, BconeApiError, BconeTokens
from .const import CONF_DEVICE_ID, CONF_EMAIL, CONF_TOKENS, DOMAIN, PLATFORMS
from .state import build_history_state_report, empty_state_report

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BCone read-only monitoring from a config entry."""

    coordinator = BconeReadonlyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a BCone config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
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

    async def _async_update_data(self) -> dict[str, Any]:
        device_id = str(self.entry.data[CONF_DEVICE_ID])
        try:
            await self._valid_tokens()
            history = await self.api.get_device_history(device_id)
            return build_history_state_report(history, device_id=device_id)
        except (BconeApiError, ClientResponseError) as exc:
            raise UpdateFailed(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - coordinator should surface unexpected failures.
            raise UpdateFailed(str(exc)) from exc

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
