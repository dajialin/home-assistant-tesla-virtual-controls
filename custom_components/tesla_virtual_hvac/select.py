"""Local-state seat controls with Tesla Fleet command execution."""

import asyncio
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.components.tesla_fleet.helpers import handle_vehicle_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from tesla_fleet_api.const import AutoSeat, Level, Scope, Seat

from .command import TeslaCommandEntity
from .const import CONF_MQTT_CLIMATE_ON_ENTITY, DEFAULT_MQTT_CLIMATE_ON_ENTITY
from .seat_model import (
    SEAT_DEFINITIONS,
    SeatCommand,
    SeatDefinition,
    SeatFeature,
    seat_command_plan,
    vehicle_unique_id,
)
from .steering_model import (
    STEERING_OPTIONS,
    SteeringCommand,
    SteeringFeature,
    steering_command_plan,
)

SEAT_OBJECT_IDS = {
    "front_left": "tesla_front_left_seat",
    "front_right": "tesla_front_right_seat",
    "rear_left": "tesla_rear_left_seat_heater",
    "rear_right": "tesla_rear_right_seat_heater",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one command entity for each controllable seat."""
    runtime = entry.runtime_data
    scoped = Scope.VEHICLE_CMDS in runtime.scopes
    climate_on_entity = runtime.config[CONF_MQTT_CLIMATE_ON_ENTITY]
    async_add_entities(
        [
            TeslaVirtualSeat(
                runtime.vehicle,
                definition,
                scoped,
                runtime.device_info,
                climate_on_entity,
            )
            for definition in SEAT_DEFINITIONS
        ]
        + [
            TeslaVirtualSteeringWheelHeater(
                runtime.vehicle,
                scoped,
                runtime.device_info,
                climate_on_entity,
            )
        ]
    )


class TeslaVirtualSeat(TeslaCommandEntity, SelectEntity, RestoreEntity):
    """One locally restored seat control with mutually exclusive modes."""

    _attr_has_entity_name = True
    _attr_current_option: str | None = None

    def __init__(
        self,
        vehicle: Any,
        definition: SeatDefinition,
        scoped: bool,
        device_info: DeviceInfo,
        climate_on_entity: str = DEFAULT_MQTT_CLIMATE_ON_ENTITY,
    ) -> None:
        """Initialize a Tesla seat control."""
        self._definition = definition
        self._transition_lock = asyncio.Lock()
        self._climate_on_entity = climate_on_entity
        self.scoped = scoped
        super().__init__(vehicle, scoped)
        self._attr_device_info = device_info
        self._attr_options = list(definition.options)
        self._attr_unique_id = vehicle_unique_id(
            f"tesla_virtual_seat_{definition.position.value}",
            vehicle.vin,
        )
        self._attr_translation_key = definition.translation_key
        self._attr_suggested_object_id = SEAT_OBJECT_IDS[definition.position.value]
        self._attr_icon = (
            "mdi:car-seat" if definition.ventilation else "mdi:car-seat-heater"
        )

    def _climate_is_on(self) -> bool:
        """Read climate status only from the configured TeslaMate entity."""
        hass = getattr(self, "hass", None)
        return bool(hass and hass.states.is_state(self._climate_on_entity, STATE_ON))

    async def async_added_to_hass(self) -> None:
        """Restore the last successful or selected mode."""
        await super().async_added_to_hass()
        if self._attr_current_option is not None:
            return
        if (
            previous := await self.async_get_last_state()
        ) is not None and previous.state in self._attr_options:
            self._attr_current_option = previous.state

    async def async_select_option(self, option: str) -> None:
        """Apply one safe seat mode transition through Tesla Fleet."""
        async with self._transition_lock:
            await self._async_apply_option(option)

    async def _async_apply_option(self, option: str) -> None:
        """Apply one seat mode while holding the transition lock."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        commands = seat_command_plan(self._definition, option)
        await self.wake_up_if_asleep()
        if any(command.level > 0 for command in commands) and not self._climate_is_on():
            await handle_vehicle_command(self.api.auto_conditioning_start())
        for command in commands:
            await handle_vehicle_command(self._seat_command(command))
        self._attr_current_option = option
        self.async_write_ha_state()

    def _seat_command(self, command: SeatCommand) -> Any:
        """Build one Tesla Fleet command from a validated transition step."""
        if command.feature is SeatFeature.AUTO:
            if self._definition.auto_api_position is None:
                raise ValueError("Automatic seat climate is unavailable for this seat")
            return self.api.remote_auto_seat_climate_request(
                AutoSeat(self._definition.auto_api_position),
                bool(command.level),
            )
        position = Seat(self._definition.api_position)
        level = Level(command.level)
        if command.feature is SeatFeature.HEATER:
            return self.api.remote_seat_heater_request(position, level)
        return self.api.remote_seat_cooler_request(position, level)


class TeslaVirtualSteeringWheelHeater(
    TeslaCommandEntity,
    SelectEntity,
    RestoreEntity,
):
    """One locally restored steering control with exclusive modes."""

    _attr_has_entity_name = True
    _attr_current_option: str | None = None
    _attr_options = STEERING_OPTIONS
    _attr_translation_key = "steering_wheel_heater"
    _attr_icon = "mdi:steering"
    _attr_suggested_object_id = "tesla_steering_wheel_heater"

    def __init__(
        self,
        vehicle: Any,
        scoped: bool,
        device_info: DeviceInfo,
        climate_on_entity: str = DEFAULT_MQTT_CLIMATE_ON_ENTITY,
    ) -> None:
        """Initialize the steering-wheel heater."""
        self._transition_lock = asyncio.Lock()
        self._climate_on_entity = climate_on_entity
        self.scoped = scoped
        super().__init__(vehicle, scoped)
        self._attr_device_info = device_info
        self._attr_translation_key = "steering_wheel_heater"
        self._attr_options = list(STEERING_OPTIONS)
        self._attr_unique_id = vehicle_unique_id(
            "tesla_virtual_steering_wheel_heater",
            vehicle.vin,
        )

    def _climate_is_on(self) -> bool:
        """Read climate status only from the configured TeslaMate entity."""
        hass = getattr(self, "hass", None)
        return bool(hass and hass.states.is_state(self._climate_on_entity, STATE_ON))

    async def async_added_to_hass(self) -> None:
        """Restore the last successful or selected mode."""
        await super().async_added_to_hass()
        if self._attr_current_option is not None:
            return
        if (
            previous := await self.async_get_last_state()
        ) is not None and previous.state in self._attr_options:
            self._attr_current_option = previous.state

    async def async_select_option(self, option: str) -> None:
        """Apply one safe steering-wheel mode transition."""
        async with self._transition_lock:
            await self._async_apply_option(option)

    async def _async_apply_option(self, option: str) -> None:
        """Apply one steering mode while holding the transition lock."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        commands = steering_command_plan(option)
        await self.wake_up_if_asleep()
        for command in commands:
            if (
                command.feature is SteeringFeature.HEATER
                and int(command.value) > 0
                and not self._climate_is_on()
            ):
                await handle_vehicle_command(self.api.auto_conditioning_start())
            await handle_vehicle_command(self._steering_command(command))
        self._attr_current_option = option
        self.async_write_ha_state()

    def _steering_command(self, command: SteeringCommand) -> Any:
        """Build one Tesla Fleet steering-wheel command."""
        if command.feature is SteeringFeature.AUTO:
            return self.api.remote_auto_steering_wheel_heat_climate_request(
                on=bool(command.value)
            )
        return self.api.remote_steering_wheel_heat_level_request(int(command.value))
