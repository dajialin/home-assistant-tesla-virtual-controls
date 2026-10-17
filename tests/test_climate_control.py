"""TeslaMate-backed climate command behavior."""

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)

from custom_components.tesla_virtual_hvac.climate import TeslaVirtualHvac
from custom_components.tesla_virtual_hvac.const import (
    CONF_FLEET_ENTITY,
    CONF_MQTT_CLIMATE_ON_ENTITY,
    CONF_MQTT_CURRENT_TEMPERATURE_ENTITY,
    CONF_MQTT_PRESET_ENTITY,
    CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
)


class ClimateControlTests(unittest.TestCase):
    def _entity(self) -> TeslaVirtualHvac:
        entity = TeslaVirtualHvac(
            {
                CONF_FLEET_ENTITY: "climate.climate",
                CONF_MQTT_CLIMATE_ON_ENTITY: "binary_sensor.tesla_is_climate_on",
                CONF_MQTT_CURRENT_TEMPERATURE_ENTITY: "sensor.tesla_inside_temp",
                CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY: "sensor.tesla_driver_temp",
                CONF_MQTT_PRESET_ENTITY: "sensor.tesla_climate_keeper_mode",
            }
        )
        entity.hass = SimpleNamespace(services=SimpleNamespace(async_call=AsyncMock()))
        entity.async_write_ha_state = MagicMock()
        return entity

    @staticmethod
    def _state(entity_id: str, state: str, changed_at: datetime):
        return SimpleNamespace(
            entity_id=entity_id,
            state=state,
            last_changed=changed_at,
        )

    def test_hvac_optimism_survives_unrelated_source_then_yields_to_hvac(self) -> None:
        entity = self._entity()
        initial = datetime(2026, 9, 4, tzinfo=timezone.utc)
        entity._observe_state(
            self._state("binary_sensor.tesla_is_climate_on", "off", initial)
        )
        entity._observe_state(self._state("sensor.tesla_inside_temp", "30", initial))
        entity._apply_snapshot()

        asyncio.run(entity.async_set_hvac_mode(HVACMode.HEAT_COOL))

        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "command")

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "binary_sensor.tesla_is_climate_on",
                        "off",
                        initial + timedelta(milliseconds=250),
                    )
                }
            )
        )
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "command")

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "binary_sensor.tesla_is_climate_on",
                        "unavailable",
                        initial + timedelta(milliseconds=500),
                    )
                }
            )
        )
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "command")

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "binary_sensor.tesla_is_climate_on",
                        "off",
                        initial + timedelta(milliseconds=750),
                    )
                }
            )
        )
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "command")

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "sensor.tesla_inside_temp",
                        "31",
                        initial + timedelta(seconds=1),
                    )
                }
            )
        )
        self.assertEqual(entity.current_temperature, 31)
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "command")

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "binary_sensor.tesla_is_climate_on",
                        "on",
                        initial + timedelta(seconds=2),
                    )
                }
            )
        )
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "mqtt")

    def test_target_optimism_survives_unrelated_source_then_yields_to_target(
        self,
    ) -> None:
        entity = self._entity()
        initial = datetime(2026, 9, 4, tzinfo=timezone.utc)
        entity._observe_state(self._state("sensor.tesla_driver_temp", "22", initial))
        entity._observe_state(self._state("sensor.tesla_inside_temp", "30", initial))
        entity._apply_snapshot()

        asyncio.run(entity.async_set_temperature(temperature=24))

        self.assertEqual(entity.target_temperature, 24)
        self.assertEqual(
            entity.extra_state_attributes["target_temperature_source"],
            "command",
        )

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "sensor.tesla_inside_temp",
                        "31",
                        initial + timedelta(seconds=1),
                    )
                }
            )
        )
        self.assertEqual(entity.target_temperature, 24)
        self.assertEqual(
            entity.extra_state_attributes["target_temperature_source"],
            "command",
        )

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "sensor.tesla_driver_temp",
                        "23",
                        initial + timedelta(seconds=2),
                    )
                }
            )
        )
        self.assertEqual(entity.target_temperature, 23)
        self.assertEqual(
            entity.extra_state_attributes["target_temperature_source"],
            "teslamate",
        )

    def test_preset_optimism_clears_independently_per_source_field(self) -> None:
        entity = self._entity()
        initial = datetime(2026, 9, 4, tzinfo=timezone.utc)
        entity._observe_state(
            self._state("binary_sensor.tesla_is_climate_on", "off", initial)
        )
        entity._observe_state(
            self._state("sensor.tesla_climate_keeper_mode", "off", initial)
        )
        entity._apply_snapshot()

        asyncio.run(entity.async_set_preset_mode("dog"))

        entity.hass.services.async_call.assert_awaited_once_with(
            "climate",
            SERVICE_SET_PRESET_MODE,
            {
                "entity_id": "climate.climate",
                ATTR_PRESET_MODE: "dog",
            },
            blocking=True,
            context=entity._context,
        )
        self.assertEqual(entity.preset_mode, "dog")
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["preset_mode_source"], "command")
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "command")

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "sensor.tesla_climate_keeper_mode",
                        "dog",
                        initial + timedelta(seconds=1),
                    )
                }
            )
        )
        self.assertEqual(entity.preset_mode, "dog")
        self.assertEqual(entity.extra_state_attributes["preset_mode_source"], "mqtt")
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "command")

        entity._async_source_changed(
            SimpleNamespace(
                data={
                    "new_state": self._state(
                        "binary_sensor.tesla_is_climate_on",
                        "on",
                        initial + timedelta(seconds=2),
                    )
                }
            )
        )
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "mqtt")

    def test_turn_off_optimistically_clears_hvac_and_preset(self) -> None:
        entity = self._entity()
        initial = datetime(2026, 9, 4, tzinfo=timezone.utc)
        entity._observe_state(
            self._state("binary_sensor.tesla_is_climate_on", "on", initial)
        )
        entity._observe_state(
            self._state("sensor.tesla_climate_keeper_mode", "keep", initial)
        )
        entity._apply_snapshot()

        asyncio.run(entity.async_turn_off())

        self.assertEqual(entity.hvac_mode, HVACMode.OFF)
        self.assertEqual(entity.preset_mode, "off")
        self.assertEqual(entity.extra_state_attributes["hvac_mode_source"], "command")
        self.assertEqual(entity.extra_state_attributes["preset_mode_source"], "command")

    def test_failed_climate_command_keeps_source_state(self) -> None:
        entity = self._entity()
        initial = datetime(2026, 9, 4, tzinfo=timezone.utc)
        entity._observe_state(self._state("sensor.tesla_driver_temp", "22", initial))
        entity._apply_snapshot()
        entity.hass.services.async_call.side_effect = RuntimeError("command rejected")

        with self.assertRaisesRegex(RuntimeError, "command rejected"):
            asyncio.run(entity.async_set_temperature(temperature=24))

        self.assertEqual(entity.target_temperature, 22)
        self.assertEqual(
            entity.extra_state_attributes["target_temperature_source"],
            "teslamate",
        )
        entity.async_write_ha_state.assert_not_called()

    def test_climate_commands_are_serialized_across_fields(self) -> None:
        entity = self._entity()
        initial = datetime(2026, 9, 4, tzinfo=timezone.utc)
        entity._observe_state(
            self._state("binary_sensor.tesla_is_climate_on", "off", initial)
        )
        entity._observe_state(self._state("sensor.tesla_driver_temp", "22", initial))
        entity._apply_snapshot()

        async def run_commands() -> bool:
            first_command_waiting = asyncio.Event()
            release_first_command = asyncio.Event()

            async def controlled_call(_domain, service, _data, **_kwargs) -> None:
                if service == SERVICE_SET_HVAC_MODE:
                    first_command_waiting.set()
                    await release_first_command.wait()

            entity.hass.services.async_call.side_effect = controlled_call
            hvac_task = asyncio.create_task(
                entity.async_set_hvac_mode(HVACMode.HEAT_COOL)
            )
            await first_command_waiting.wait()
            temperature_task = asyncio.create_task(
                entity.async_set_temperature(temperature=24)
            )
            await asyncio.sleep(0)
            temperature_started_early = entity.hass.services.async_call.await_count > 1
            release_first_command.set()
            await asyncio.gather(hvac_task, temperature_task)
            return temperature_started_early

        self.assertFalse(asyncio.run(run_commands()))
        self.assertEqual(
            entity.hass.services.async_call.await_args_list,
            [
                call(
                    "climate",
                    SERVICE_SET_HVAC_MODE,
                    {
                        "entity_id": "climate.climate",
                        ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
                    },
                    blocking=True,
                    context=entity._context,
                ),
                call(
                    "climate",
                    SERVICE_SET_TEMPERATURE,
                    {
                        "entity_id": "climate.climate",
                        ATTR_TEMPERATURE: 24,
                    },
                    blocking=True,
                    context=entity._context,
                ),
            ],
        )
        self.assertEqual(entity.hvac_mode, HVACMode.HEAT_COOL)
        self.assertEqual(entity.target_temperature, 24)


if __name__ == "__main__":
    unittest.main()
