"""Virtual Tesla vehicle lock."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant.helpers.device_registry import DeviceInfo
from tesla_fleet_api.const import Scope

from custom_components.tesla_virtual_hvac import lock
from custom_components.tesla_virtual_hvac.const import TESLAMATE_TELEMETRY_DEFAULTS


class VehicleLockTests(unittest.TestCase):
    def _runtime(self):
        vehicle = SimpleNamespace(
            vin="VIN123",
            coordinator=SimpleNamespace(data={"vehicle_state_locked": True}),
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

    def test_setup_adds_one_vehicle_lock(self) -> None:
        _vehicle, runtime = self._runtime()
        entities = []
        asyncio.run(
            lock.async_setup_entry(
                None,
                SimpleNamespace(runtime_data=runtime),
                entities.extend,
            )
        )
        self.assertEqual(len(entities), 1)
        entity = entities[0]
        self.assertEqual(entity.translation_key, "vehicle_lock")
        self.assertEqual(entity.unique_id, "tesla_virtual_vehicle_lock_VIN123")
        self.assertIsNone(entity.is_locked)
        self.assertEqual(entity.telemetry_entity_id, "binary_sensor.tesla_locked")

    def test_lock_and_unlock_use_vehicle_door_commands(self) -> None:
        vehicle, runtime = self._runtime()
        entity = lock.TeslaVirtualVehicleLock(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_locked",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        lock_result = object()
        unlock_result = object()
        vehicle.api.door_lock.return_value = lock_result
        vehicle.api.door_unlock.return_value = unlock_result
        with patch.object(lock, "handle_vehicle_command", new=AsyncMock()) as handle:
            asyncio.run(entity.async_unlock())
            asyncio.run(entity.async_lock())
        self.assertEqual(
            vehicle.api.method_calls,
            [call.door_unlock(), call.door_lock()],
        )
        self.assertEqual(
            handle.await_args_list,
            [call(unlock_result), call(lock_result)],
        )
        self.assertTrue(entity.is_locked)

    def test_opposite_vehicle_lock_commands_are_serialized(self) -> None:
        vehicle, runtime = self._runtime()
        entity = lock.TeslaVirtualVehicleLock(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_locked",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        lock_result = object()
        unlock_result = object()
        vehicle.api.door_lock.return_value = lock_result
        vehicle.api.door_unlock.return_value = unlock_result

        async def run_commands() -> bool:
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()

            async def controlled_handle(result) -> None:
                if result is lock_result:
                    first_command_waiting.set()
                    await release_first_command.wait()

            with patch.object(
                lock,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=controlled_handle),
            ):
                lock_task = asyncio.create_task(entity.async_lock())
                await first_command_waiting.wait()
                unlock_task = asyncio.create_task(entity.async_unlock())
                await asyncio.sleep(0)
                unlock_started_early = len(vehicle.api.method_calls) > 1
                release_first_command.set()
                await asyncio.gather(lock_task, unlock_task)
                return unlock_started_early

        self.assertFalse(asyncio.run(run_commands()))
        self.assertEqual(
            vehicle.api.method_calls,
            [call.door_lock(), call.door_unlock()],
        )
        self.assertFalse(entity.is_locked)

    def test_queued_unlock_runs_after_lock_command_fails(self) -> None:
        vehicle, runtime = self._runtime()
        entity = lock.TeslaVirtualVehicleLock(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_locked",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="on"))
        lock_result = object()
        unlock_result = object()
        vehicle.api.door_lock.return_value = lock_result
        vehicle.api.door_unlock.return_value = unlock_result

        async def run_commands():
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()

            async def controlled_handle(result) -> None:
                if result is lock_result:
                    first_command_waiting.set()
                    await release_first_command.wait()
                    raise RuntimeError("lock rejected")

            with patch.object(
                lock,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=controlled_handle),
            ):
                lock_task = asyncio.create_task(entity.async_lock())
                await first_command_waiting.wait()
                unlock_task = asyncio.create_task(entity.async_unlock())
                await asyncio.sleep(0)
                unlock_started_early = len(vehicle.api.method_calls) > 1
                release_first_command.set()
                outcomes = await asyncio.wait_for(
                    asyncio.gather(
                        lock_task,
                        unlock_task,
                        return_exceptions=True,
                    ),
                    timeout=1,
                )
                return unlock_started_early, outcomes

        unlock_started_early, outcomes = asyncio.run(run_commands())
        self.assertFalse(unlock_started_early)
        self.assertIsInstance(outcomes[0], RuntimeError)
        self.assertEqual(str(outcomes[0]), "lock rejected")
        self.assertIsNone(outcomes[1])
        self.assertEqual(
            vehicle.api.method_calls,
            [call.door_lock(), call.door_unlock()],
        )
        self.assertFalse(entity.is_locked)
        entity.async_write_ha_state.assert_called_once_with()

    def test_failed_lock_command_does_not_publish_optimistic_state(self) -> None:
        vehicle, runtime = self._runtime()
        entity = lock.TeslaVirtualVehicleLock(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_locked",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))
        vehicle.api.door_unlock.return_value = object()

        with (
            patch.object(
                lock,
                "handle_vehicle_command",
                new=AsyncMock(side_effect=RuntimeError("command rejected")),
            ),
            self.assertRaisesRegex(RuntimeError, "command rejected"),
        ):
            asyncio.run(entity.async_unlock())

        self.assertTrue(entity.is_locked)
        entity.async_write_ha_state.assert_not_called()

    def test_teslamate_overrides_successful_lock_optimism(self) -> None:
        vehicle, runtime = self._runtime()
        entity = lock.TeslaVirtualVehicleLock(
            vehicle,
            True,
            runtime.device_info,
            "binary_sensor.tesla_locked",
        )
        entity.wake_up_if_asleep = AsyncMock()
        entity.async_write_ha_state = MagicMock()
        entity._update_from_teslamate_state(SimpleNamespace(state="off"))
        vehicle.api.door_unlock.return_value = object()

        with patch.object(lock, "handle_vehicle_command", new=AsyncMock()):
            asyncio.run(entity.async_unlock())

        self.assertFalse(entity.is_locked)
        entity._async_teslamate_state_changed(
            SimpleNamespace(data={"new_state": SimpleNamespace(state="on")})
        )
        self.assertFalse(entity.is_locked)
        entity._async_teslamate_state_changed(
            SimpleNamespace(data={"new_state": SimpleNamespace(state="off")})
        )
        self.assertTrue(entity.is_locked)
        self.assertEqual(entity.async_write_ha_state.call_count, 3)


if __name__ == "__main__":
    unittest.main()
