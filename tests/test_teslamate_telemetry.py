"""TeslaMate telemetry is the only read path for vehicle controls."""

import unittest
from types import SimpleNamespace

from custom_components.tesla_virtual_hvac.const import (
    CONF_TESLAMATE_CHARGE_LIMIT_ENTITY,
    CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY,
    CONF_TESLAMATE_FRUNK_ENTITY,
    CONF_TESLAMATE_LOCKED_ENTITY,
    CONF_TESLAMATE_SENTRY_MODE_ENTITY,
    CONF_TESLAMATE_TRUNK_ENTITY,
    CONF_TESLAMATE_WINDOWS_ENTITY,
    DEFAULT_TESLAMATE_CHARGE_LIMIT_ENTITY,
    DEFAULT_TESLAMATE_CHARGE_PORT_DOOR_ENTITY,
    DEFAULT_TESLAMATE_FRUNK_ENTITY,
    DEFAULT_TESLAMATE_LOCKED_ENTITY,
    DEFAULT_TESLAMATE_SENTRY_MODE_ENTITY,
    DEFAULT_TESLAMATE_TRUNK_ENTITY,
    DEFAULT_TESLAMATE_WINDOWS_ENTITY,
    TESLAMATE_TELEMETRY_DEFAULTS,
)
from custom_components.tesla_virtual_hvac.telemetry import (
    binary_state,
    numeric_state,
)


class TeslaMateTelemetryTests(unittest.TestCase):
    def test_defaults_match_the_existing_teslamate_mqtt_entities(self) -> None:
        self.assertEqual(
            TESLAMATE_TELEMETRY_DEFAULTS,
            {
                CONF_TESLAMATE_TRUNK_ENTITY: DEFAULT_TESLAMATE_TRUNK_ENTITY,
                CONF_TESLAMATE_FRUNK_ENTITY: DEFAULT_TESLAMATE_FRUNK_ENTITY,
                CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY: (
                    DEFAULT_TESLAMATE_CHARGE_PORT_DOOR_ENTITY
                ),
                CONF_TESLAMATE_WINDOWS_ENTITY: DEFAULT_TESLAMATE_WINDOWS_ENTITY,
                CONF_TESLAMATE_LOCKED_ENTITY: DEFAULT_TESLAMATE_LOCKED_ENTITY,
                CONF_TESLAMATE_SENTRY_MODE_ENTITY: (
                    DEFAULT_TESLAMATE_SENTRY_MODE_ENTITY
                ),
                CONF_TESLAMATE_CHARGE_LIMIT_ENTITY: (
                    DEFAULT_TESLAMATE_CHARGE_LIMIT_ENTITY
                ),
            },
        )
        self.assertEqual(
            set(TESLAMATE_TELEMETRY_DEFAULTS.values()),
            {
                "binary_sensor.tesla_trunk_open",
                "binary_sensor.tesla_frunk_open",
                "binary_sensor.tesla_charge_port_door_open",
                "binary_sensor.tesla_windows_open",
                "binary_sensor.tesla_locked",
                "binary_sensor.tesla_sentry_mode",
                "sensor.tesla_charge_limit_soc",
            },
        )

    def test_binary_state_parses_only_valid_home_assistant_states(self) -> None:
        self.assertTrue(binary_state(SimpleNamespace(state="on")))
        self.assertFalse(binary_state(SimpleNamespace(state="off")))
        self.assertIsNone(binary_state(SimpleNamespace(state="unknown")))
        self.assertIsNone(binary_state(SimpleNamespace(state="unavailable")))
        self.assertIsNone(binary_state(None))

    def test_numeric_state_rejects_unknown_non_finite_and_boolean_values(self) -> None:
        self.assertEqual(numeric_state(SimpleNamespace(state="80")), 80.0)
        self.assertEqual(numeric_state(SimpleNamespace(state="50.5")), 50.5)
        self.assertIsNone(numeric_state(SimpleNamespace(state="unknown")))
        self.assertIsNone(numeric_state(SimpleNamespace(state="nan")))
        self.assertIsNone(numeric_state(SimpleNamespace(state="on")))
        self.assertIsNone(numeric_state(None))


if __name__ == "__main__":
    unittest.main()
