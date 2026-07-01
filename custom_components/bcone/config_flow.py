"""Config flow for the BCone read-only integration."""

from __future__ import annotations

import uuid
import logging
from typing import Any

from aiohttp import ClientResponseError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BconeApiClient, BconeApiError, BconeAuthError, BconeDeviceNotFound
from .const import CONF_DEVICE_ID, CONF_EMAIL, CONF_MOBILE_DEVICE_ID, CONF_NAME, CONF_TOKENS, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BconeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a credential-only BCone read-only monitor."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""

        return BconeOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create a config entry from BCone account credentials."""

        errors: dict[str, str] = {}
        if user_input is not None:
            email = str(user_input.get(CONF_EMAIL, "")).strip().lower()
            password = str(user_input.get(CONF_PASSWORD, ""))
            mobile_device_id = uuid.uuid4().hex
            api = BconeApiClient(async_get_clientsession(self.hass))
            try:
                tokens = await api.authenticate(email, password)
                device_id = await api.discover_device_id(email, mobile_device_id, tokens)
            except BconeAuthError:
                errors["base"] = "invalid_auth"
            except BconeDeviceNotFound:
                errors["base"] = "no_device"
            except (BconeApiError, ClientResponseError) as exc:
                _LOGGER.debug("BCone setup failed during API connection/discovery: %s", exc)
                errors["base"] = "cannot_connect"
            except Exception as exc:  # noqa: BLE001 - HA config flow maps unknown setup failures.
                _LOGGER.exception("Unexpected BCone setup failure: %s", exc)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_NAME: DEFAULT_NAME,
                        CONF_EMAIL: email,
                        CONF_MOBILE_DEVICE_ID: mobile_device_id,
                        CONF_DEVICE_ID: device_id,
                        CONF_TOKENS: tokens.as_dict(),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class BconeOptionsFlow(config_entries.OptionsFlow):
    """Placeholder options flow for future read-only transport settings."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """No user-editable options are needed for credential-only read-only monitoring."""

        return self.async_create_entry(title="", data={})
