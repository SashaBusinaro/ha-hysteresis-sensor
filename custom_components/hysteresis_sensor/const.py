"""Constants for the Hysteresis Filter Sensor integration."""

from typing import Final

DOMAIN: Final = "hysteresis_sensor"

CONF_NAME: Final = "name"
CONF_SOURCE_ENTITY_ID: Final = "source_entity_id"
CONF_THRESHOLD_TYPE: Final = "threshold_type"
CONF_THRESHOLD_VALUE: Final = "threshold_value"

THRESHOLD_ABSOLUTE: Final = "Absolute"
THRESHOLD_PERCENTAGE: Final = "Percentage"
