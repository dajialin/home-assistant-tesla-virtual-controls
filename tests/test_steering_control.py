"""Combined steering-wheel heater control requirements."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant.helpers.device_registry import DeviceInfo
from tesla_fleet_api.const import Scope

from custom_components.tesla_virtual_hvac import select
from custom_components.tesla_virtual_hvac.const import (
    CONF_MQTT_CLIMATE_ON_ENTITY,
    DEFAULT_MQTT_CLIMATE_ON_ENTITY,
)
from custom_components.tesla_virtual_hvac.steering_model import (
    STEERING_OPTIONS,
    SteeringCommand,
    SteeringFeature,
    steering_command_plan,
    steering_option_from_values,
)


class SteeringModelTests(unittest.TestCase):
    def test_options_are_off_low_high_auto(self) -> None:
        self.assertEqual(STEERING_OPTIONS, ["off", "low", "high", "auto"])

    def test_auto_telemetry_has_precedence(self) -> None:
        self.assertEqual(steering_option_from_values(0, True), "auto")
        self.assertEqual(steering_option_from_values(2, True), "auto")
        self.assertEqual(steering_option_from_values(0, False), "off")
        self.assertEqual(steering_option_from_values(1, False), "low")
        self.assertEqual(steering_option_from_values(2, False), "high")
        self.assertIsNone(steering_option_from_values(3, False))

    def test_command_plans_keep_auto_and_manual_modes_exclusive(self) -> None:
        self.assertEqual(
            steering_command_plan("auto"),
            (
                SteeringCommand(SteeringFeature.HEATER, 0),
                SteeringCommand(SteeringFeature.AUTO, True),
            ),
        )
        self.assertEqual(
            steering_command_plan("off"),
            (
                SteeringCommand(SteeringFeature.AUTO, False),
                SteeringCommand(SteeringFeature.HEATER, 0),
            ),
        )
        self.assertEqual(
            steering_command_plan("low"),
            (
                SteeringCommand(SteeringFeature.AUTO, False),
                SteeringCommand(SteeringFeature.HEATER, 1),
            ),
        )
        self.assertEqual(
            steering_command_plan("high"),
            (
                SteeringCommand(SteeringFeature.AUTO, False),
                SteeringCommand(SteeringFeature.HEATER, 2),
            ),
        )


class SteeringRuntimeTests(unittest.TestCase):
    def _runtime(self, *, climate_on: bool = True):
        coordinator = SimpleNamespace(
            data={
                "climate_state_is_climate_on": climate_on,
                "climate_state_steering_wheel_heat_level": 0,
                "climate_state_auto_steering_wheel_heat": True,
                "climate_state_seat_heater_left": 0,
                "climate_state_seat_fan_front_left": 0,
                "climate_state_auto_seat_climate_left": False,
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

    def test_select_setup_adds_one_combined_steering_entity(self) -> None:
        _vehicle, runtime = self._runtime()
        entities = []
        asyncio.run(
            select.async_setup_entry(
                None,
                SimpleNamespace(runtime_data=runtime),
                entities.extend,
            )
        )
        steering = [
            entity
            for entity in entities
            if entity.translation_key == "steering_wheel_heater"
        ]
        self.assertEqual(len(entities), 5)
        self.assertEqual(len(steering), 1)
        self.assertEqual(steering[0].options, STEERING_OPTIONS)
        self.assertIsNone(steering[0].current_option)
        self.assertEqual(
            steering[0].unique_id,
            "tesla_virtual_steering_wheel_heater_VIN123",
        )

    def test_selecting_auto_disables_manual_level_before_auto(self) -> None:
        vehicle, runtime = self._runtime()
        entity = select.TeslaVirtualSteeringWheelHeater(
            vehicle,
            True,
            runtime.device_info,
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        manual_result = object()
        auto_result = object()
        vehicle.api.remote_steering_wheel_heat_level_request.return_value = (
            manual_result
        )
        vehicle.api.remote_auto_steering_wheel_heat_climate_request.return_value = (
            auto_result
        )
        with patch.object(select, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_select_option("auto"))
        self.assertEqual(
            vehicle.api.method_calls,
            [
                call.remote_steering_wheel_heat_level_request(0),
                call.remote_auto_steering_wheel_heat_climate_request(on=True),
            ],
        )
        self.assertEqual(
            handle.await_args_list,
            [call(manual_result), call(auto_result)],
        )

    def test_selecting_high_starts_hvac_then_sets_manual_level(self) -> None:
        vehicle, runtime = self._runtime(climate_on=False)
        entity = select.TeslaVirtualSteeringWheelHeater(
            vehicle,
            True,
            runtime.device_info,
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        auto_off_result = object()
        climate_result = object()
        heater_result = object()
        vehicle.api.remote_auto_steering_wheel_heat_climate_request.return_value = (
            auto_off_result
        )
        vehicle.api.auto_conditioning_start.return_value = climate_result
        vehicle.api.remote_steering_wheel_heat_level_request.return_value = (
            heater_result
        )
        with patch.object(select, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_select_option("high"))
        self.assertEqual(
            vehicle.api.method_calls,
            [
                call.remote_auto_steering_wheel_heat_climate_request(on=False),
                call.auto_conditioning_start(),
                call.remote_steering_wheel_heat_level_request(2),
            ],
        )
        self.assertEqual(
            handle.await_args_list,
            [call(auto_off_result), call(climate_result), call(heater_result)],
        )

    def test_failed_transition_stops_before_hvac_or_manual_heat(self) -> None:
        vehicle, runtime = self._runtime(climate_on=False)
        entity = select.TeslaVirtualSteeringWheelHeater(
            vehicle,
            True,
            runtime.device_info,
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        vehicle.api.remote_auto_steering_wheel_heat_climate_request.return_value = (
            object()
        )
        with (
            patch.object(
                select,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=RuntimeError("command failed")),
            ),
            self.assertRaisesRegex(RuntimeError, "command failed"),
        ):
            asyncio.run(entity.async_select_option("high"))
        self.assertEqual(
            vehicle.api.method_calls,
            [call.remote_auto_steering_wheel_heat_climate_request(on=False)],
        )
        entity.async_write_ha_state.assert_not_called()

    def test_concurrent_transitions_do_not_interleave_commands(self) -> None:
        vehicle, runtime = self._runtime()
        entity = select.TeslaVirtualSteeringWheelHeater(
            vehicle,
            True,
            runtime.device_info,
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._climate_is_on = MagicMock(return_value=True)

        async def yield_after_command(_result):
            await asyncio.sleep(0)

        async def run_transitions() -> None:
            await asyncio.gather(
                entity.async_select_option("auto"),
                entity.async_select_option("high"),
            )

        with patch.object(
            select,
            "handle_vehicle_command",
            new=AsyncMock(side_effect=yield_after_command),
        ):
            asyncio.run(run_transitions())

        auto_then_high = [
            call.remote_steering_wheel_heat_level_request(0),
            call.remote_auto_steering_wheel_heat_climate_request(on=True),
            call.remote_auto_steering_wheel_heat_climate_request(on=False),
            call.remote_steering_wheel_heat_level_request(2),
        ]
        high_then_auto = [
            call.remote_auto_steering_wheel_heat_climate_request(on=False),
            call.remote_steering_wheel_heat_level_request(2),
            call.remote_steering_wheel_heat_level_request(0),
            call.remote_auto_steering_wheel_heat_climate_request(on=True),
        ]
        self.assertIn(vehicle.api.method_calls, (auto_then_high, high_then_auto))


if __name__ == "__main__":
    unittest.main()
