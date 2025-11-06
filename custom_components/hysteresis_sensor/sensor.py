"""Hysteresis Filter Sensor platform."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Hysteresis Filter Sensor from a config entry."""
    async_add_entities([HysteresisSensorEntity(hass, entry)])


class HysteresisSensorEntity(SensorEntity, RestoreEntity):
    """A sensor that only updates when change exceeds a threshold."""

    _attr_should_poll = False
    _attr_available = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        data = entry.data
        opts = entry.options
        self._name: str = data[CONF_NAME]
        self._source_entity_id: str = data[CONF_SOURCE_ENTITY_ID]
        # Read thresholds from options first, fallback to data
        self._threshold_type: str = opts.get(
            CONF_THRESHOLD_TYPE, data[CONF_THRESHOLD_TYPE]
        )
        self._threshold_value: float = float(
            opts.get(CONF_THRESHOLD_VALUE, data[CONF_THRESHOLD_VALUE])
        )

        # Persistent record of the last numeric value we reported
        self._last_recorded_numeric: float | None = None

        # Entity presentation
        self._attr_name = self._name
        raw_uid = f"{self._source_entity_id}|{self._name}"
        self._attr_unique_id = hashlib.sha256(raw_uid.encode()).hexdigest()

        # Attributes inherited from source
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_native_unit_of_measurement = None

        self._unsub: Callable[[], None] | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"source_entity_id": self._source_entity_id}

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to source updates."""
        # Restore last state
        last = await self.async_get_last_state()
        if last is not None:
            restored_state = last.state
            # Try to restore numeric memory and display value
            num = _to_float(restored_state)
            if num is not None:
                self._last_recorded_numeric = num
                self._attr_native_value = num
                self._attr_available = True
            else:
                # Mirror non-numeric restored state
                self._apply_non_numeric_state(restored_state)

        # On first run without a valid last numeric, adopt current source
        if self._last_recorded_numeric is None:
            src_state = self.hass.states.get(self._source_entity_id)
            if src_state is not None:
                self._update_inherited_attributes(src_state.attributes)
                num = _to_float(src_state.state)
                if num is not None:
                    self._last_recorded_numeric = num
                    self._attr_native_value = num
                    self._attr_available = True
                else:
                    self._apply_non_numeric_state(src_state.state)
        else:
            # If we restored a numeric value but the current source is non-numeric
            # (e.g., unknown/unavailable at startup), mirror that state immediately
            src_state = self.hass.states.get(self._source_entity_id)
            if src_state is not None:
                self._update_inherited_attributes(src_state.attributes)
                if _to_float(src_state.state) is None:
                    self._apply_non_numeric_state(src_state.state)

        # Listen for state changes
        self._unsub = async_track_state_change_event(
            self.hass, [self._source_entity_id], self._handle_source_event
        )

        # Ensure state is written after initial setup
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_source_event(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            # Entity removed; treat as unknown
            self._attr_native_value = STATE_UNKNOWN
            self.async_write_ha_state()
            return

        # Update inherited attributes every time
        self._update_inherited_attributes(new_state.attributes)

        new_val_str = new_state.state
        new_num = _to_float(new_val_str)

        # If source is non-numeric -> propagate immediately
        if new_num is None:
            self._apply_non_numeric_state(new_val_str)
            self.async_write_ha_state()
            return

        # Initial adoption if we don't have a last numeric
        if self._last_recorded_numeric is None:
            self._last_recorded_numeric = new_num
            self._attr_native_value = new_num
            self._attr_available = True
            self.async_write_ha_state()
            return

        delta = abs(new_num - self._last_recorded_numeric)

        if self._threshold_type == THRESHOLD_ABSOLUTE:
            should_update = delta > self._threshold_value
            _LOGGER.debug(
                "Hysteresis sensor %s: absolute threshold check - delta: %s, threshold: %s, should_update: %s",
                self._name,
                delta,
                self._threshold_value,
                should_update,
            )
        else:  # THRESHOLD_PERCENTAGE
            ref = abs(self._last_recorded_numeric)
            pct = (self._threshold_value / 100.0) * ref
            should_update = delta > pct
            _LOGGER.debug(
                "Hysteresis sensor %s: percentage threshold check - delta: %s, pct_threshold: %s (%.1f%%), should_update: %s",
                self._name,
                delta,
                pct,
                self._threshold_value,
                should_update,
            )

        if should_update:
            _LOGGER.debug(
                "Hysteresis sensor %s: threshold exceeded, updating from %s to %s",
                self._name,
                self._last_recorded_numeric,
                new_num,
            )
            self._last_recorded_numeric = new_num
            self._attr_native_value = new_num
            self.async_write_ha_state()

    def _update_inherited_attributes(self, attrs: dict[str, Any]) -> None:
        self._attr_native_unit_of_measurement = attrs.get("unit_of_measurement")
        self._attr_device_class = attrs.get("device_class")
        self._attr_state_class = attrs.get("state_class")

    def _apply_non_numeric_state(self, state_str: str) -> None:
        if state_str == STATE_UNAVAILABLE:
            self._attr_available = False
            self._attr_native_value = None
        elif state_str == STATE_UNKNOWN:
            self._attr_available = True
            self._attr_native_value = None
        else:
            # Fallback: set state as-is and consider entity available
            self._attr_available = True
            self._attr_native_value = state_str


def _to_float(value: Any) -> float | None:
    if value in (None, STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
