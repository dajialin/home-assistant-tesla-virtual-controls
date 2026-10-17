"""Runtime entities read state from TeslaMate and reserve Fleet for commands."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from tesla_fleet_api.const import Scope

from custom_components.tesla_virtual_hvac import (
    climate,
    cover,
    lock,
    number,
    switch,
)
from custom_components.tesla_virtual_hvac.const import (
    CONF_FLEET_ENTITY,
    CONF_MQTT_CLIMATE_ON_ENTITY,
    CONF_MQTT_CURRENT_TEMPERATURE_ENTITY,
    CONF_MQTT_PRESET_ENTITY,
    CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
)


class TeslaMateRuntimeTests(unittest.TestCase):
    def _vehicle(self):
        coordinator = SimpleNamespace(
            data={
                "vehicle_state_rt": 1,
                "vehicle_state_ft": 1,
                "charge_state_charge_port_door_open": True,
                "vehicle_state_fd_window": 1,
                "vehicle_state_fp_window": 1,
                "vehicle_state_rd_window": 1,
                "vehicle_state_rp_window": 1,
                "vehicle_state_locked": False,
                "vehicle_state_sentry_mode": True,
                "charge_state_charge_limit_soc": 55,
            }
        )
        return SimpleNamespace(
            vin="VIN123",
            coordinator=coordinator,
            api=MagicMock(),
            device=DeviceInfo(identifiers={("tesla_fleet", "VIN123")}),
        )

    def _device(self) -> DeviceInfo:
        return DeviceInfo(identifiers={("tesla_virtual_hvac", "VIN123")})

    def test_covers_follow_teslamate_even_when_fleet_data_disagrees(self) -> None:
        vehicle = self._vehicle()
        entities = [
            cover.TeslaVirtualRearTrunk(
                vehicle,
                True,
                self._device(),
                "binary_sensor.tesla_trunk_open",
            ),
            cover.TeslaVirtualFrontTrunk(
                vehicle,
                True,
                self._device(),
                "binary_sensor.tesla_frunk_open",
            ),
            cover.TeslaVirtualChargePortDoor(
                vehicle,
                [Scope.VEHICLE_CMDS],
                self._device(),
                "binary_sensor.tesla_charge_port_door_open",
            ),
            cover.TeslaVirtualWindows(
                vehicle,
                True,
                self._device(),
                "binary_sensor.tesla_windows_open",
            ),
        ]
        for entity in entities:
            with self.subTest(entity=type(entity).__name__):
                entity._update_from_teslamate_state(SimpleNamespace(state="off"))
                self.assertTrue(entity.is_closed)
                entity._update_from_teslamate_state(SimpleNamespace(state="on"))
                self.assertFalse(entity.is_closed)
                entity._update_from_teslamate_state(
                    SimpleNamespace(state="unavailable")
                )
                self.assertIsNone(entity.is_closed)

    def test_lock_switch_and_number_follow_teslamate(self) -> None:
        vehicle = self._vehicle()
        vehicle_lock = lock.TeslaVirtualVehicleLock(
            vehicle,
            True,
            self._device(),
            "binary_sensor.tesla_locked",
        )
        sentry = switch.TeslaVirtualSentryMode(
            vehicle,
            True,
            self._device(),
            "binary_sensor.tesla_sentry_mode",
        )
        charge_limit = number.TeslaVirtualChargeLimit(
            vehicle,
            [Scope.VEHICLE_CMDS],
            self._device(),
            "sensor.tesla_charge_limit_soc",
        )

        vehicle_lock._update_from_teslamate_state(SimpleNamespace(state="on"))
        self.assertFalse(vehicle_lock.is_locked)
        vehicle_lock._update_from_teslamate_state(SimpleNamespace(state="off"))
        self.assertTrue(vehicle_lock.is_locked)
        vehicle_lock._update_from_teslamate_state(SimpleNamespace(state="unknown"))
        self.assertIsNone(vehicle_lock.is_locked)

        sentry._update_from_teslamate_state(SimpleNamespace(state="off"))
        charge_limit._update_from_teslamate_state(SimpleNamespace(state="82"))

        self.assertFalse(sentry.is_on)
        self.assertEqual(charge_limit.native_value, 82)

    def test_climate_observes_teslamate_but_not_fleet_state(self) -> None:
        entity = climate.TeslaVirtualHvac(
            {
                CONF_FLEET_ENTITY: "climate.climate",
                CONF_MQTT_CLIMATE_ON_ENTITY: "binary_sensor.tesla_is_climate_on",
                CONF_MQTT_CURRENT_TEMPERATURE_ENTITY: "sensor.tesla_inside_temp",
                CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY: "sensor.tesla_driver_temp",
                CONF_MQTT_PRESET_ENTITY: "sensor.tesla_climate_keeper_mode",
            }
        )
        self.assertNotIn("climate.climate", entity._source_entities)
        self.assertEqual(
            entity._source_entities,
            {
                "binary_sensor.tesla_is_climate_on",
                "sensor.tesla_inside_temp",
                "sensor.tesla_driver_temp",
                "sensor.tesla_climate_keeper_mode",
            },
        )

    def test_command_entities_never_register_or_refresh_fleet_coordinator(self) -> None:
        vehicle = self._vehicle()
        vehicle.coordinator.async_add_listener = MagicMock()
        vehicle.coordinator.async_request_refresh = MagicMock()
        entities = [
            cover.TeslaVirtualRearTrunk(
                vehicle,
                True,
                self._device(),
                "binary_sensor.tesla_trunk_open",
            ),
            lock.TeslaVirtualVehicleLock(
                vehicle,
                True,
                self._device(),
                "binary_sensor.tesla_locked",
            ),
            number.TeslaVirtualChargeLimit(
                vehicle,
                [Scope.VEHICLE_CMDS],
                self._device(),
                "sensor.tesla_charge_limit_soc",
            ),
            switch.TeslaVirtualSentryMode(
                vehicle,
                True,
                self._device(),
                "binary_sensor.tesla_sentry_mode",
            ),
        ]

        for entity in entities:
            with self.subTest(entity=type(entity).__name__):
                self.assertNotIsInstance(entity, CoordinatorEntity)
                self.assertFalse(hasattr(entity, "async_update"))

        vehicle.coordinator.async_add_listener.assert_not_called()
        vehicle.coordinator.async_request_refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
