"""Config flow for Hysteresis Filter Sensor."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_NAME,
    CONF_SOURCE_ENTITY_ID,
    CONF_THRESHOLD_TYPE,
    CONF_THRESHOLD_VALUE,
    DOMAIN,
    THRESHOLD_ABSOLUTE,
    THRESHOLD_PERCENTAGE,
)

_LOGGER = logging.getLogger(__name__)


class HysteresisSensorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hysteresis Filter Sensor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate source entity exists
            if not self.hass.states.get(user_input[CONF_SOURCE_ENTITY_ID]):
                errors["source_entity_id"] = "entity_not_found"

            # Validate threshold value
            if user_input[CONF_THRESHOLD_VALUE] <= 0:
                errors["threshold_value"] = "invalid_threshold"

            if not errors:
                # Build a stable unique id using name+source
                raw_uid = f"{user_input[CONF_SOURCE_ENTITY_ID]}|{user_input[CONF_NAME]}"
                unique_id = hashlib.sha256(raw_uid.encode()).hexdigest()
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                _LOGGER.debug("Creating hysteresis sensor: %s", user_input[CONF_NAME])
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector({"text": {}}),
                vol.Required(CONF_SOURCE_ENTITY_ID): selector(
                    {"entity": {"domain": "sensor"}}
                ),
                vol.Required(CONF_THRESHOLD_TYPE, default=THRESHOLD_ABSOLUTE): selector(
                    {"select": {"options": [THRESHOLD_ABSOLUTE, THRESHOLD_PERCENTAGE]}}
                ),
                vol.Required(CONF_THRESHOLD_VALUE, default=1.0): selector(
                    {"number": {"min": 0, "step": 0.01, "mode": "box"}}
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:  # type: ignore[override]
        """Return the options flow handler for this integration."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for an existing entry (thresholds only)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Store the config entry for options updates."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options for the integration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate threshold value
            if user_input[CONF_THRESHOLD_VALUE] <= 0:
                errors["threshold_value"] = "invalid_threshold"

            if not errors:
                _LOGGER.debug(
                    "Updating options for hysteresis sensor: %s",
                    self.config_entry.title,
                )
                # Save new options (will trigger reload via update listener)
                return self.async_create_entry(title="", data=user_input)

        current_type = self.config_entry.options.get(
            CONF_THRESHOLD_TYPE,
            self.config_entry.data.get(CONF_THRESHOLD_TYPE, THRESHOLD_ABSOLUTE),
        )
        current_value = self.config_entry.options.get(
            CONF_THRESHOLD_VALUE,
            self.config_entry.data.get(CONF_THRESHOLD_VALUE, 1.0),
        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_THRESHOLD_TYPE, default=current_type): selector(
                    {"select": {"options": [THRESHOLD_ABSOLUTE, THRESHOLD_PERCENTAGE]}}
                ),
                vol.Required(CONF_THRESHOLD_VALUE, default=current_value): selector(
                    {"number": {"min": 0, "step": 0.01, "mode": "box"}}
                ),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
