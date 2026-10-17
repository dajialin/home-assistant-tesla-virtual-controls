"""Virtual Tesla cover controls."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from tesla_fleet_api.const import Scope, Trunk, WindowCommand

from custom_components.tesla_virtual_hvac import cover
from custom_components.tesla_virtual_hvac.const import TESLAMATE_TELEMETRY_DEFAULTS


class CoverRuntimeTests(unittest.TestCase):
    def _runtime(self):
        coordinator = SimpleNamespace(
            data={
                "vehicle_state_rt": 0,
                "vehicle_state_ft": 0,
                "charge_state_charge_port_door_open": False,
                "vehicle_state_fd_window": 0,
                "vehicle_state_fp_window": 0,
                "vehicle_state_rd_window": 0,
                "vehicle_state_rp_window": 0,
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
            scopes=[Scope.VEHICLE_CMDS, Scope.VEHICLE_CHARGING_CMDS],
            device_info=DeviceInfo(identifiers={("tesla_virtual_hvac", "VIN123")}),
            config=dict(TESLAMATE_TELEMETRY_DEFAULTS),
        )
        return vehicle, runtime

    def test_setup_adds_all_four_vehicle_covers(self) -> None:
        _vehicle, runtime = self._runtime()
        entities = []
        asyncio.run(
            cover.async_setup_entry(
                None,
                SimpleNamespace(runtime_data=runtime),
                entities.extend,
            )
        )
        self.assertEqual(len(entities), 4)
        by_key = {entity.translation_key: entity for entity in entities}
        self.assertEqual(
            set(by_key),
            {"trunk", "frunk", "charge_port_door", "windows"},
        )
        trunk = by_key["trunk"]
        self.assertEqual(trunk.unique_id, "tesla_virtual_trunk_VIN123")
        self.assertIsNone(trunk.is_closed)
        self.assertEqual(trunk.telemetry_entity_id, "binary_sensor.tesla_trunk_open")
        self.assertEqual(
            trunk.supported_features,
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
        )
        frunk = by_key["frunk"]
        self.assertEqual(frunk.unique_id, "tesla_virtual_frunk_VIN123")
        self.assertIsNone(frunk.is_closed)
        self.assertEqual(frunk.supported_features, CoverEntityFeature.OPEN)
        charge_port = by_key["charge_port_door"]
        self.assertEqual(
            charge_port.unique_id,
            "tesla_virtual_charge_port_door_VIN123",
        )
        self.assertIsNone(charge_port.is_closed)
        self.assertEqual(
            charge_port.supported_features,
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
        )
        windows = by_key["windows"]
        self.assertEqual(windows.unique_id, "tesla_virtual_windows_VIN123")
        self.assertIsNone(windows.is_closed)
        self.assertEqual(
            windows.supported_features,
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
        )

    def test_rear_trunk_open_and_close_use_toggle_only_when_needed(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualRearTrunk(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_trunk_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))
        command_result = object()
        vehicle.api.actuate_trunk.return_value = command_result
        with patch.object(cover, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_open_cover())
            asyncio.run(entity.async_open_cover())
            asyncio.run(entity.async_close_cover())
        self.assertEqual(
            vehicle.api.method_calls,
            [
                call.actuate_trunk(Trunk.REAR),
                call.actuate_trunk(Trunk.REAR),
            ],
        )
        self.assertEqual(
            handle.await_args_list,
            [call(command_result), call(command_result)],
        )
        self.assertTrue(entity.is_closed)

    def test_rear_trunk_opposite_commands_are_serialized(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualRearTrunk(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_trunk_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))
        command_result = object()
        vehicle.api.actuate_trunk.return_value = command_result

        async def run_commands() -> bool:
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()
            command_count = 0

            async def controlled_handle(_result) -> None:
                nonlocal command_count
                command_count += 1
                if command_count == 1:
                    first_command_waiting.set()
                    await release_first_command.wait()

            with patch.object(
                cover,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=controlled_handle),
            ):
                open_task = asyncio.create_task(entity.async_open_cover())
                await first_command_waiting.wait()
                close_task = asyncio.create_task(entity.async_close_cover())
                await asyncio.sleep(0)
                close_started_early = len(vehicle.api.method_calls) > 1
                release_first_command.set()
                await asyncio.gather(open_task, close_task)
                return close_started_early

        self.assertFalse(asyncio.run(run_commands()))
        self.assertEqual(
            vehicle.api.method_calls,
            [
                call.actuate_trunk(Trunk.REAR),
                call.actuate_trunk(Trunk.REAR),
            ],
        )
        self.assertTrue(entity.is_closed)

    def test_front_trunk_is_open_only_and_calls_front_api(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualFrontTrunk(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_frunk_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))
        command_result = object()
        vehicle.api.actuate_trunk.return_value = command_result
        with patch.object(cover, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_open_cover())
            asyncio.run(entity.async_open_cover())
        self.assertEqual(
            vehicle.api.method_calls,
            [call.actuate_trunk(Trunk.FRONT)],
        )
        self.assertEqual(handle.await_args_list, [call(command_result)])
        self.assertFalse(entity.is_closed)

    def test_front_trunk_duplicate_open_commands_are_serialized(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualFrontTrunk(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_frunk_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))
        command_result = object()
        vehicle.api.actuate_trunk.return_value = command_result

        async def run_commands() -> bool:
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()
            command_count = 0

            async def controlled_handle(_result) -> None:
                nonlocal command_count
                command_count += 1
                if command_count == 1:
                    first_command_waiting.set()
                    await release_first_command.wait()

            with patch.object(
                cover,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=controlled_handle),
            ):
                first_open = asyncio.create_task(entity.async_open_cover())
                await first_command_waiting.wait()
                second_open = asyncio.create_task(entity.async_open_cover())
                await asyncio.sleep(0)
                duplicate_started = len(vehicle.api.method_calls) > 1
                release_first_command.set()
                await asyncio.gather(first_open, second_open)
                return duplicate_started

        self.assertFalse(asyncio.run(run_commands()))
        self.assertEqual(
            vehicle.api.method_calls,
            [call.actuate_trunk(Trunk.FRONT)],
        )
        self.assertFalse(entity.is_closed)

    def test_charge_port_door_uses_dedicated_open_and_close_commands(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualChargePortDoor(
            vehicle,
            runtime.scopes,
            runtime.device_info,
            "binary_sensor.tesla_charge_port_door_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        open_result = object()
        close_result = object()
        vehicle.api.charge_port_door_open.return_value = open_result
        vehicle.api.charge_port_door_close.return_value = close_result
        with patch.object(cover, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_open_cover())
            asyncio.run(entity.async_close_cover())
        self.assertEqual(
            vehicle.api.method_calls,
            [call.charge_port_door_open(), call.charge_port_door_close()],
        )
        self.assertEqual(
            handle.await_args_list,
            [call(open_result), call(close_result)],
        )
        self.assertTrue(entity.is_closed)

    def test_charge_port_opposite_commands_are_serialized(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualChargePortDoor(
            vehicle,
            runtime.scopes,
            runtime.device_info,
            "binary_sensor.tesla_charge_port_door_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        open_result = object()
        close_result = object()
        vehicle.api.charge_port_door_open.return_value = open_result
        vehicle.api.charge_port_door_close.return_value = close_result

        async def run_commands() -> bool:
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()

            async def controlled_handle(result) -> None:
                if result is open_result:
                    first_command_waiting.set()
                    await release_first_command.wait()

            with patch.object(
                cover,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=controlled_handle),
            ):
                open_task = asyncio.create_task(entity.async_open_cover())
                await first_command_waiting.wait()
                close_task = asyncio.create_task(entity.async_close_cover())
                await asyncio.sleep(0)
                close_started_early = len(vehicle.api.method_calls) > 1
                release_first_command.set()
                await asyncio.gather(open_task, close_task)
                return close_started_early

        self.assertFalse(asyncio.run(run_commands()))
        self.assertEqual(
            vehicle.api.method_calls,
            [call.charge_port_door_open(), call.charge_port_door_close()],
        )
        self.assertTrue(entity.is_closed)

    def test_windows_vent_and_close_use_window_control(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualWindows(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_windows_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        vent_result = object()
        close_result = object()
        vehicle.api.window_control.side_effect = [vent_result, close_result]
        with patch.object(cover, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_open_cover())
            asyncio.run(entity.async_close_cover())
        self.assertEqual(
            vehicle.api.method_calls,
            [
                call.window_control(command=WindowCommand.VENT),
                call.window_control(command=WindowCommand.CLOSE),
            ],
        )
        self.assertEqual(
            handle.await_args_list,
            [call(vent_result), call(close_result)],
        )
        self.assertTrue(entity.is_closed)

    def test_window_opposite_commands_are_serialized(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualWindows(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_windows_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        vent_result = object()
        close_result = object()
        vehicle.api.window_control.side_effect = [vent_result, close_result]

        async def run_commands() -> bool:
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()

            async def controlled_handle(result) -> None:
                if result is vent_result:
                    first_command_waiting.set()
                    await release_first_command.wait()

            with patch.object(
                cover,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=controlled_handle),
            ):
                vent_task = asyncio.create_task(entity.async_open_cover())
                await first_command_waiting.wait()
                close_task = asyncio.create_task(entity.async_close_cover())
                await asyncio.sleep(0)
                close_started_early = len(vehicle.api.method_calls) > 1
                release_first_command.set()
                await asyncio.gather(vent_task, close_task)
                return close_started_early

        self.assertFalse(asyncio.run(run_commands()))
        self.assertEqual(
            vehicle.api.method_calls,
            [
                call.window_control(command=WindowCommand.VENT),
                call.window_control(command=WindowCommand.CLOSE),
            ],
        )
        self.assertTrue(entity.is_closed)

    def test_windows_state_is_open_when_any_window_is_open(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualWindows(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_windows_open",
        )
        entity._update_from_teslamate_state(SimpleNamespace(state="on"))
        self.assertFalse(entity.is_closed)
        entity._update_from_teslamate_state(SimpleNamespace(state="unavailable"))
        self.assertIsNone(entity.is_closed)

    def test_teslamate_overrides_successful_window_optimism(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualWindows(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_windows_open",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))
        vehicle.api.window_control.return_value = object()

        with patch.object(cover, "handle_vehicle_command", new=AsyncMock()):
            asyncio.run(entity.async_open_cover())

        self.assertFalse(entity.is_closed)
        entity._async_teslamate_state_changed(
            SimpleNamespace(data={"new_state": SimpleNamespace(state="on")})
        )
        self.assertFalse(entity.is_closed)
        entity._async_teslamate_state_changed(
            SimpleNamespace(data={"new_state": SimpleNamespace(state="off")})
        )
        self.assertTrue(entity.is_closed)
        self.assertEqual(entity.async_write_ha_state.call_count, 3)

    def test_failed_cover_commands_do_not_publish_optimistic_state(self) -> None:
        factories = (
            lambda vehicle, runtime: cover.TeslaVirtualWindows(
                vehicle,
                True,
                runtime.device_info,
                "binary_sensor.tesla_windows_open",
            ),
            lambda vehicle, runtime: cover.TeslaVirtualChargePortDoor(
                vehicle,
                runtime.scopes,
                runtime.device_info,
                "binary_sensor.tesla_charge_port_door_open",
            ),
            lambda vehicle, runtime: cover.TeslaVirtualFrontTrunk(
                vehicle,
                True,
                runtime.device_info,
                "binary_sensor.tesla_frunk_open",
            ),
            lambda vehicle, runtime: cover.TeslaVirtualRearTrunk(
                vehicle,
                True,
                runtime.device_info,
                "binary_sensor.tesla_trunk_open",
            ),
        )

        for factory in factories:
            vehicle, runtime = self._runtime()
            entity = factory(vehicle, runtime)
            entity.wake_up_if_asleep = AsyncMock()
            entity.async_write_ha_state = MagicMock()
            entity._update_from_teslamate_state(SimpleNamespace(state="off"))
            with (
                self.subTest(entity=type(entity).__name__),
                patch.object(
                    cover,
                    "handle_vehicle_command",
                    new=AsyncMock(side_effect=RuntimeError("command rejected")),
                ),
                self.assertRaisesRegex(RuntimeError, "command rejected"),
            ):
                asyncio.run(entity.async_open_cover())
            self.assertTrue(entity.is_closed)
            entity.async_write_ha_state.assert_not_called()

    def test_toggle_trunks_recheck_state_after_wake(self) -> None:
        factories = (
            (
                cover.TeslaVirtualFrontTrunk,
                "binary_sensor.tesla_frunk_open",
            ),
            (
                cover.TeslaVirtualRearTrunk,
                "binary_sensor.tesla_trunk_open",
            ),
        )

        for entity_type, source_entity_id in factories:
            vehicle, runtime = self._runtime()
            entity = entity_type(
                vehicle,
                True,
                runtime.device_info,
                source_entity_id,
            )
            entity._update_from_teslamate_state(SimpleNamespace(state="off"))
            entity.async_write_ha_state = MagicMock()

            async def source_reaches_requested_state() -> None:
                entity._update_from_teslamate_state(SimpleNamespace(state="on"))

            entity.wake_up_if_asleep = AsyncMock(
                side_effect=source_reaches_requested_state
            )
            with (
                self.subTest(entity=entity_type.__name__),
                patch.object(
                    cover, "handle_vehicle_command", new=AsyncMock()
                ) as handle,
            ):
                asyncio.run(entity.async_open_cover())
            vehicle.api.actuate_trunk.assert_not_called()
            handle.assert_not_awaited()
            self.assertFalse(entity.is_closed)

    def test_rear_trunk_close_rechecks_state_after_wake(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualRearTrunk(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_trunk_open",
        )
        entity._update_from_teslamate_state(SimpleNamespace(state="on"))
        entity.async_write_ha_state = MagicMock()

        async def source_reaches_requested_state() -> None:
            entity._update_from_teslamate_state(SimpleNamespace(state="off"))

        entity.wake_up_if_asleep = AsyncMock(side_effect=source_reaches_requested_state)
        with patch.object(cover, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_close_cover())

        vehicle.api.actuate_trunk.assert_not_called()
        handle.assert_not_awaited()
        self.assertTrue(entity.is_closed)

    def test_rear_trunk_close_fails_closed_if_state_becomes_unknown_during_wake(
        self,
    ) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualRearTrunk(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_trunk_open",
        )
        entity._update_from_teslamate_state(SimpleNamespace(state="on"))

        async def source_becomes_unknown() -> None:
            entity._update_from_teslamate_state(SimpleNamespace(state="unavailable"))

        entity.wake_up_if_asleep = AsyncMock(side_effect=source_becomes_unknown)
        with (
            patch.object(cover, "handle_vehicle_command", new=AsyncMock()) as handle,
            self.assertRaises(ServiceValidationError),
        ):
            asyncio.run(entity.async_close_cover())

        vehicle.api.actuate_trunk.assert_not_called()
        handle.assert_not_awaited()
        self.assertIsNone(entity.is_closed)

    def test_toggle_trunks_fail_closed_if_state_becomes_unknown_during_wake(
        self,
    ) -> None:
        factories = (
            (
                cover.TeslaVirtualFrontTrunk,
                "binary_sensor.tesla_frunk_open",
            ),
            (
                cover.TeslaVirtualRearTrunk,
                "binary_sensor.tesla_trunk_open",
            ),
        )

        for entity_type, source_entity_id in factories:
            vehicle, runtime = self._runtime()
            entity = entity_type(
                vehicle,
                True,
                runtime.device_info,
                source_entity_id,
            )
            entity._update_from_teslamate_state(SimpleNamespace(state="off"))

            async def source_becomes_unknown() -> None:
                entity._update_from_teslamate_state(
                    SimpleNamespace(state="unavailable")
                )

            entity.wake_up_if_asleep = AsyncMock(side_effect=source_becomes_unknown)
            with (
                self.subTest(entity=entity_type.__name__),
                patch.object(
                    cover, "handle_vehicle_command", new=AsyncMock()
                ) as handle,
                self.assertRaises(ServiceValidationError),
            ):
                asyncio.run(entity.async_open_cover())
            vehicle.api.actuate_trunk.assert_not_called()
            handle.assert_not_awaited()
            self.assertIsNone(entity.is_closed)

    def test_toggle_trunk_commands_fail_closed_when_teslamate_is_unknown(self) -> None:
        vehicle, runtime = self._runtime()
        entity = cover.TeslaVirtualRearTrunk(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_trunk_open",
        )
        entity.wake_up_if_asleep = AsyncMock()

        with self.assertRaises(ServiceValidationError):
            asyncio.run(entity.async_open_cover())
        with self.assertRaises(ServiceValidationError):
            asyncio.run(entity.async_close_cover())

        vehicle.api.actuate_trunk.assert_not_called()
        entity.wake_up_if_asleep.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
