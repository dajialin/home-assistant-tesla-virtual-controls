"""Runtime contract for four virtual seat entities with front auto mode."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant.helpers.device_registry import DeviceInfo
from tesla_fleet_api.const import AutoSeat, Level, Scope, Seat

from custom_components.tesla_virtual_hvac import select
from custom_components.tesla_virtual_hvac.const import (
    CONF_MQTT_CLIMATE_ON_ENTITY,
    DEFAULT_MQTT_CLIMATE_ON_ENTITY,
)
from custom_components.tesla_virtual_hvac.seat_model import SEAT_DEFINITIONS


class SeatRuntimeTests(unittest.TestCase):
    def _runtime(self):
        coordinator = SimpleNamespace(
            data={
                "climate_state_is_climate_on": True,
                "climate_state_seat_heater_left": 0,
                "climate_state_seat_fan_front_left": 0,
                "climate_state_auto_seat_climate_left": True,
                "climate_state_seat_heater_right": 0,
                "climate_state_seat_fan_front_right": 0,
                "climate_state_auto_seat_climate_right": False,
                "climate_state_seat_heater_rear_left": 0,
                "climate_state_seat_heater_rear_right": 0,
            }
        )
        vehicle = SimpleNamespace(
            vin="VIN123",
            coordinator=coordinator,
            api=MagicMock(),
            device=DeviceInfo(identifiers={("tesla_fleet", "VIN123")}),
        )
        runtime = SimpleNamespace(
            vehicle=vehicle,
            scopes=[Scope.VEHICLE_CMDS],
            device_info=DeviceInfo(identifiers={("tesla_virtual_hvac", "VIN123")}),
            config={CONF_MQTT_CLIMATE_ON_ENTITY: DEFAULT_MQTT_CLIMATE_ON_ENTITY},
        )
        return vehicle, runtime

    def test_setup_creates_exactly_four_seat_entities(self) -> None:
        _vehicle, runtime = self._runtime()
        entities = []
        entry = SimpleNamespace(runtime_data=runtime)

        asyncio.run(select.async_setup_entry(None, entry, entities.extend))

        seats = [
            entity for entity in entities if entity.translation_key.startswith("seat_")
        ]
        self.assertEqual(len(seats), 4)
        self.assertEqual(
            [entity.translation_key for entity in seats],
            [
                "seat_front_left",
                "seat_front_right",
                "seat_rear_left",
                "seat_rear_right",
            ],
        )

    def test_front_entity_ignores_fleet_telemetry(self) -> None:
        vehicle, runtime = self._runtime()
        entity = select.TeslaVirtualSeat(
            vehicle,
            SEAT_DEFINITIONS[0],
            True,
            runtime.device_info,
        )

        self.assertIsNone(entity.current_option)

    def test_selecting_auto_uses_auto_seat_api_after_manual_modes_are_off(self) -> None:
        vehicle, runtime = self._runtime()
        entity = select.TeslaVirtualSeat(
            vehicle,
            SEAT_DEFINITIONS[0],
            True,
            runtime.device_info,
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._climate_is_on = MagicMock(return_value=True)
        heater_result = object()
        cooler_result = object()
        auto_result = object()
        vehicle.api.remote_seat_heater_request.return_value = heater_result
        vehicle.api.remote_seat_cooler_request.return_value = cooler_result
        vehicle.api.remote_auto_seat_climate_request.return_value = auto_result

        with patch.object(select, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_select_option("auto"))

        self.assertEqual(
            vehicle.api.method_calls,
            [
                call.remote_seat_heater_request(Seat.FRONT_LEFT, Level.OFF),
                call.remote_seat_cooler_request(Seat.FRONT_LEFT, Level.OFF),
                call.remote_auto_seat_climate_request(AutoSeat.FRONT_LEFT, True),
            ],
        )
        self.assertEqual(
            handle.await_args_list,
            [call(heater_result), call(cooler_result), call(auto_result)],
        )
        self.assertEqual(entity.current_option, "auto")


if __name__ == "__main__":
    unittest.main()
