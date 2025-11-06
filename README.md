<div align="center">

# Hysteresis Filter Sensor

Reduce database writes from “chatty” sensors by only recording significant changes.

</div>

## What it does

This custom integration adds a sensor platform that mirrors another sensor’s state, but only updates when the change is greater than a configured threshold:

- Absolute threshold: update when |new − last_recorded| > value
- Percentage threshold: update when |new − last_recorded| > |last_recorded| × (value / 100)

It restores its last recorded state on Home Assistant restarts, preventing spurious updates on boot. Non‑numeric states (unknown, unavailable) are always propagated immediately.

## Example use cases

- Temperature or power sensors that report tiny fluctuations multiple times per minute
- Battery percentage sensors with 0.1% steps

### Database optimization (recorder)

To actually reduce database writes, configure the [Recorder](https://www.home-assistant.io/integrations/recorder) to exclude the original noisy source sensor while keeping the new filtered sensor included.

Example (configuration.yaml):

```yaml
recorder:
  exclude:
    entities:
      # Stop recording the original, noisy sensor
      - sensor.chatty_power_meter
```

Do not exclude the filtered sensor entity. Restart Home Assistant after changing the configuration.

## Installation

### HACS (recommended)

1. In HACS, add this repository as a custom integration repository.
2. Install “Hysteresis Filter Sensor”.
3. Restart Home Assistant.

### Manual

1. Copy the folder `custom_components/hysteresis_sensor/` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration (UI only)

Settings are added via Settings → Devices & Services → “Add Integration” → “Hysteresis Filter Sensor”.

You’ll be asked for:

- Name: Friendly name for the filtered sensor
- Source entity: The sensor to monitor (entity selector)
- Threshold type: Absolute or Percentage
- Threshold value: Numeric threshold value

The integration will create a new sensor that:

- Inherits unit_of_measurement, device_class, state_class from the source when available
- Adds an attribute `source_entity_id` to show what it monitors

## How it works

Core logic:

1. If the source state is non‑numeric (unknown/unavailable), the filter sensor updates immediately to match.
2. If the filter sensor has no stored numeric state (first run or failed restore), it adopts the current source value immediately.
3. Otherwise, it calculates the delta from its last recorded numeric value and only updates when it exceeds the configured threshold (absolute or percentage).

## Troubleshooting

- If the sensor never updates, double‑check the threshold type/value and ensure the source produces numeric states.
- If attributes (unit, class) don’t appear, ensure they are provided by the source sensor.

## License

MIT — see `LICENSE`.
