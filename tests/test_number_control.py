"""Virtual Tesla charge-limit number."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant.components.number import NumberDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from tesla_fleet_api.const import Scope

from custom_components.tesla_virtual_hvac import number
from custom_components.tesla_virtual_hvac.const import TESLAMATE_TELEMETRY_DEFAULTS


class ChargeLimitTests(unittest.TestCase):
    def _runtime(self):
        vehicle = SimpleNamespace(
            vin="VIN123",
            coordinator=SimpleNamespace(
                data={
                    "charge_state_charge_limit_soc": 80,
                    "charge_state_charge_limit_soc_min": 50,
                    "charge_state_charge_limit_soc_max": 100,
                }
            ),
            api=MagicMock(),
            device=DeviceInfo(identifiers={("tesla_fleet", "VIN123")}),
        )
        runtime = SimpleNamespace(
            vehicle=vehicle,
            scopes=[Scope.VEHICLE_CMDS, Scope.VEHICLE_CHARGING_CMDS],
            device_info=DeviceInfo(identifiers={("tesla_virtual_hvac", "VIN123")}),
            config=dict(TESLAMATE_TELEMETRY_DEFAULTS),
        )
        return vehicle, runtime

    def test_setup_adds_charge_limit_with_live_bounds(self) -> None:
        _vehicle, runtime = self._runtime()
        entities = []
        asyncio.run(
            number.async_setup_entry(
                None,
                SimpleNamespace(runtime_data=runtime),
                entities.extend,
            )
        )
        self.assertEqual(len(entities), 1)
        entity = entities[0]
        self.assertEqual(entity.translation_key, "charge_limit")
        self.assertEqual(entity.unique_id, "tesla_virtual_charge_limit_VIN123")
        self.assertIsNone(entity.native_value)
        self.assertEqual(entity.native_min_value, 50)
        self.assertEqual(entity.native_max_value, 100)
        self.assertEqual(entity.native_step, 1)
        self.assertEqual(entity.device_class, NumberDeviceClass.BATTERY)

    def test_setting_charge_limit_calls_fleet_api(self) -> None:
        vehicle, runtime = self._runtime()
        entity = number.TeslaVirtualChargeLimit(
            vehicle,
            runtime.scopes,
            runtime.device_info,
            "sensor.tesla_charge_limit_soc",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        command_result = object()
        vehicle.api.set_charge_limit.return_value = command_result
        with patch.object(number, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_set_native_value(90))
        self.assertEqual(vehicle.api.method_calls, [call.set_charge_limit(90)])
        self.assertEqual(handle.await_args_list, [call(command_result)])
        self.assertEqual(entity.native_value, 90)

    def test_charge_limit_commands_are_serialized_in_invocation_order(self) -> None:
        vehicle, runtime = self._runtime()
        entity = number.TeslaVirtualChargeLimit(
            vehicle,
            runtime.scopes,
            runtime.device_info,
            "sensor.tesla_charge_limit_soc",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        first_result = object()
        second_result = object()
        vehicle.api.set_charge_limit.side_effect = [first_result, second_result]

        async def run_commands() -> bool:
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()

            async def controlled_handle(result) -> None:
                if result is first_result:
                    first_command_waiting.set()
                    await release_first_command.wait()

            with patch.object(
                number,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=controlled_handle),
            ):
                first_task = asyncio.create_task(entity.async_set_native_value(80))
                await first_command_waiting.wait()
                second_task = asyncio.create_task(entity.async_set_native_value(90))
                await asyncio.sleep(0)
                second_started_early = len(vehicle.api.method_calls) > 1
                release_first_command.set()
                await asyncio.gather(first_task, second_task)
                return second_started_early

        self.assertFalse(asyncio.run(run_commands()))
        self.assertEqual(
            vehicle.api.method_calls,
            [call.set_charge_limit(80), call.set_charge_limit(90)],
        )
        self.assertEqual(entity.native_value, 90)

    def test_failed_charge_limit_command_keeps_teslamate_value(self) -> None:
        vehicle, runtime = self._runtime()
        entity = number.TeslaVirtualChargeLimit(
            vehicle,
            runtime.scopes,
            runtime.device_info,
            "sensor.tesla_charge_limit_soc",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="80"))
        vehicle.api.set_charge_limit.return_value = object()

        with (
            patch.object(
                number,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=RuntimeError("command rejected")),
            ),
            self.assertRaisesRegex(RuntimeError, "command rejected"),
        ):
            asyncio.run(entity.async_set_native_value(90))

        self.assertEqual(entity.native_value, 80)
        entity.async_write_ha_state.assert_not_called()

    def test_teslamate_overrides_successful_charge_limit_optimism(self) -> None:
        vehicle, runtime = self._runtime()
        entity = number.TeslaVirtualChargeLimit(
            vehicle,
            runtime.scopes,
            runtime.device_info,
            "sensor.tesla_charge_limit_soc",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="80"))
        vehicle.api.set_charge_limit.return_value = object()

        with patch.object(number, "handle_vehicle_command", new=AsyncMock()):
            asyncio.run(entity.async_set_native_value(90))

        self.assertEqual(entity.native_value, 90)
        entity._async_teslamate_state_changed(
            SimpleNamespace(data={"new_state": SimpleNamespace(state="90")})
        )
        self.assertEqual(entity.native_value, 90)
        entity._async_teslamate_state_changed(
            SimpleNamespace(data={"new_state": SimpleNamespace(state="85")})
        )
        self.assertEqual(entity.native_value, 85)
        self.assertEqual(entity.async_write_ha_state.call_count, 3)


if __name__ == "__main__":
    unittest.main()
