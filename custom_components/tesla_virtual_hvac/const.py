"""Constants for Tesla Virtual Controls."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "tesla_virtual_hvac"
PLATFORMS: Final = [
    Platform.CLIMATE,
    Platform.COVER,
    Platform.SWITCH,
    Platform.LOCK,
    Platform.NUMBER,
]

CONF_FLEET_ENTITY = "fleet_entity"
CONF_MQTT_CLIMATE_ON_ENTITY = "mqtt_climate_on_entity"
CONF_MQTT_CURRENT_TEMPERATURE_ENTITY = "mqtt_current_temperature_entity"
CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY = "teslamate_target_temperature_entity"
CONF_MQTT_PRESET_ENTITY = "mqtt_preset_entity"
CONF_TESLAMATE_TRUNK_ENTITY = "teslamate_trunk_entity"
CONF_TESLAMATE_FRUNK_ENTITY = "teslamate_frunk_entity"
CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY = "teslamate_charge_port_door_entity"
CONF_TESLAMATE_WINDOWS_ENTITY = "teslamate_windows_entity"
CONF_TESLAMATE_LOCKED_ENTITY = "teslamate_locked_entity"
CONF_TESLAMATE_SENTRY_MODE_ENTITY = "teslamate_sentry_mode_entity"
CONF_TESLAMATE_CHARGE_LIMIT_ENTITY = "teslamate_charge_limit_entity"

# Legacy v1 option removed by async_migrate_entry.
CONF_SEAT_POSITION = "seat_position"

DEFAULT_NAME = "Tesla Controls"
LEGACY_DEFAULT_NAME = "Tesla Virtual HVAC"
LEGACY_DEFAULT_NAMES = frozenset({LEGACY_DEFAULT_NAME, "Tesla Virtual Controls"})
DEFAULT_MODEL = "Controls"
LEGACY_DEFAULT_MODEL = "Virtual HVAC"
LEGACY_DEFAULT_MODELS = frozenset({LEGACY_DEFAULT_MODEL, "Virtual Controls"})
DEFAULT_UNIQUE_ID = "tesla_virtual_hvac"
DEFAULT_FLEET_ENTITY = "climate.climate"
DEFAULT_MQTT_CLIMATE_ON_ENTITY = "binary_sensor.tesla_is_climate_on"
DEFAULT_MQTT_CURRENT_TEMPERATURE_ENTITY = "sensor.tesla_inside_temp"
DEFAULT_TESLAMATE_TARGET_TEMPERATURE_ENTITY = "sensor.tesla_driver_temp"
DEFAULT_MQTT_PRESET_ENTITY = "sensor.tesla_climate_keeper_mode"
DEFAULT_TESLAMATE_TRUNK_ENTITY = "binary_sensor.tesla_trunk_open"
DEFAULT_TESLAMATE_FRUNK_ENTITY = "binary_sensor.tesla_frunk_open"
DEFAULT_TESLAMATE_CHARGE_PORT_DOOR_ENTITY = "binary_sensor.tesla_charge_port_door_open"
DEFAULT_TESLAMATE_WINDOWS_ENTITY = "binary_sensor.tesla_windows_open"
DEFAULT_TESLAMATE_LOCKED_ENTITY = "binary_sensor.tesla_locked"
DEFAULT_TESLAMATE_SENTRY_MODE_ENTITY = "binary_sensor.tesla_sentry_mode"
DEFAULT_TESLAMATE_CHARGE_LIMIT_ENTITY = "sensor.tesla_charge_limit_soc"

TESLAMATE_TELEMETRY_DEFAULTS: Final = {
    CONF_TESLAMATE_TRUNK_ENTITY: DEFAULT_TESLAMATE_TRUNK_ENTITY,
    CONF_TESLAMATE_FRUNK_ENTITY: DEFAULT_TESLAMATE_FRUNK_ENTITY,
    CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY: (DEFAULT_TESLAMATE_CHARGE_PORT_DOOR_ENTITY),
    CONF_TESLAMATE_WINDOWS_ENTITY: DEFAULT_TESLAMATE_WINDOWS_ENTITY,
    CONF_TESLAMATE_LOCKED_ENTITY: DEFAULT_TESLAMATE_LOCKED_ENTITY,
    CONF_TESLAMATE_SENTRY_MODE_ENTITY: DEFAULT_TESLAMATE_SENTRY_MODE_ENTITY,
    CONF_TESLAMATE_CHARGE_LIMIT_ENTITY: DEFAULT_TESLAMATE_CHARGE_LIMIT_ENTITY,
}

RETIRED_COMFORT_UNIQUE_ID_BASES: Final = (
    "tesla_virtual_seat_front_left",
    "tesla_virtual_seat_front_right",
    "tesla_virtual_seat_rear_left",
    "tesla_virtual_seat_rear_right",
    "tesla_virtual_steering_wheel_heater",
)


# Stable unique IDs remain unchanged; only human-facing entity IDs are migrated.
LEGACY_ENTITY_IDS: Final = {
    DEFAULT_UNIQUE_ID: "climate.tesla_virtual_hvac",
    "tesla_virtual_trunk": "cover.tesla_virtual_trunk",
    "tesla_virtual_frunk": "cover.tesla_virtual_frunk",
    "tesla_virtual_charge_port_door": "cover.tesla_virtual_charge_port_door",
    "tesla_virtual_windows": "cover.tesla_virtual_windows",
    "tesla_virtual_sentry_mode": "switch.tesla_virtual_sentry_mode",
    "tesla_virtual_vehicle_lock": "lock.tesla_virtual_vehicle_lock",
    "tesla_virtual_charge_limit": "number.tesla_virtual_charge_limit",
}

ENTITY_ID_TARGETS: Final = {
    DEFAULT_UNIQUE_ID: "climate.tesla_climate",
    "tesla_virtual_trunk": "cover.tesla_trunk",
    "tesla_virtual_frunk": "cover.tesla_frunk",
    "tesla_virtual_charge_port_door": "cover.tesla_charge_port_door",
    "tesla_virtual_windows": "cover.tesla_windows",
    "tesla_virtual_sentry_mode": "switch.tesla_sentry_mode",
    "tesla_virtual_vehicle_lock": "lock.tesla_vehicle",
    "tesla_virtual_charge_limit": "number.tesla_charge_limit",
}

PRESET_MODES = ["off", "keep", "dog", "camp"]
