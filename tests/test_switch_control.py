"""Virtual Tesla sentry-mode switch."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant.helpers.device_registry import DeviceInfo
from tesla_fleet_api.const import Scope

from custom_components.tesla_virtual_hvac import switch
from custom_components.tesla_virtual_hvac.const import TESLAMATE_TELEMETRY_DEFAULTS


class SentrySwitchTests(unittest.TestCase):
    def _runtime(self):
        vehicle = SimpleNamespace(
            vin="VIN123",
            coordinator=SimpleNamespace(data={"vehicle_state_sentry_mode": False}),
            api=MagicMock(),
            device=DeviceInfo(identifiers={("tesla_fleet", "VIN123")}),
        )
        runtime = SimpleNamespace(
            vehicle=vehicle,
            scopes=[Scope.VEHICLE_CMDS],
            device_info=DeviceInfo(identifiers={("tesla_virtual_hvac", "VIN123")}),
            config=dict(TESLAMATE_TELEMETRY_DEFAULTS),
        )
        return vehicle, runtime

    def test_setup_adds_one_sentry_switch(self) -> None:
        _vehicle, runtime = self._runtime()
        entities = []
        asyncio.run(
            switch.async_setup_entry(
                None,
                SimpleNamespace(runtime_data=runtime),
                entities.extend,
            )
        )
        self.assertEqual(len(entities), 1)
        entity = entities[0]
        self.assertEqual(entity.translation_key, "sentry_mode")
        self.assertEqual(entity.unique_id, "tesla_virtual_sentry_mode_VIN123")
        self.assertIsNone(entity.is_on)

    def test_successful_commands_optimistically_update_sentry_state(self) -> None:
        vehicle, runtime = self._runtime()
        entity = switch.TeslaVirtualSentryMode(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_sentry_mode",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        on_result = object()
        off_result = object()
        vehicle.api.set_sentry_mode.side_effect = [on_result, off_result]
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))
        with patch.object(switch, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_turn_on())
            self.assertTrue(entity.is_on)
            entity._update_from_teslamate_state(SimpleNamespace(state="on"))
            asyncio.run(entity.async_turn_off())
        self.assertEqual(
            vehicle.api.method_calls,
            [call.set_sentry_mode(on=True), call.set_sentry_mode(on=False)],
        )
        self.assertEqual(
            handle.await_args_list,
            [call(on_result), call(off_result)],
        )
        self.assertFalse(entity.is_on)
        self.assertEqual(entity.async_write_ha_state.call_count, 2)

    def test_teslamate_change_overrides_optimistic_sentry_state(self) -> None:
        vehicle, runtime = self._runtime()
        entity = switch.TeslaVirtualSentryMode(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_sentry_mode",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        vehicle.api.set_sentry_mode.return_value = object()

        with patch.object(switch, "handle_vehicle_command", new=AsyncMock()):
            asyncio.run(entity.async_turn_on())

        self.assertTrue(entity.is_on)
        entity._async_teslamate_state_changed(
            SimpleNamespace(data={"new_state": SimpleNamespace(state="off")})
        )
        self.assertFalse(entity.is_on)
        self.assertEqual(entity.async_write_ha_state.call_count, 2)

    def test_opposite_sentry_commands_are_serialized_in_invocation_order(self) -> None:
        vehicle, runtime = self._runtime()
        entity = switch.TeslaVirtualSentryMode(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_sentry_mode",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        on_result = object()
        off_result = object()
        vehicle.api.set_sentry_mode.side_effect = [on_result, off_result]

        async def run_commands() -> bool:
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()

            async def controlled_handle(result) -> None:
                if result is on_result:
                    first_command_waiting.set()
                    await release_first_command.wait()

            with patch.object(
                switch,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=controlled_handle),
            ):
                turn_on = asyncio.create_task(entity.async_turn_on())
                await first_command_waiting.wait()
                turn_off = asyncio.create_task(entity.async_turn_off())
                await asyncio.sleep(0)
                commands_overlapped = len(vehicle.api.method_calls) > 1
                release_first_command.set()
                await asyncio.gather(turn_on, turn_off)
                return commands_overlapped

        self.assertFalse(asyncio.run(run_commands()))
        self.assertEqual(
            vehicle.api.method_calls,
            [call.set_sentry_mode(on=True), call.set_sentry_mode(on=False)],
        )
        self.assertFalse(entity.is_on)

    def test_failed_sentry_command_does_not_update_state(self) -> None:
        vehicle, runtime = self._runtime()
        entity = switch.TeslaVirtualSentryMode(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_sentry_mode",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        vehicle.api.set_sentry_mode.return_value = object()
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))

        with (
            patch.object(
                switch,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=RuntimeError("command rejected")),
            ),
            self.assertRaisesRegex(RuntimeError, "command rejected"),
        ):
            asyncio.run(entity.async_turn_on())

        self.assertFalse(entity.is_on)
        entity.async_write_ha_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
