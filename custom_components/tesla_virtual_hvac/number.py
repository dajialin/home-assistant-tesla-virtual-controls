"""TeslaMate-state charge limit with Tesla Fleet command execution."""

from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.components.tesla_fleet.helpers import handle_vehicle_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, PRECISION_WHOLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from tesla_fleet_api.const import Scope

from .command import TeslaCommandEntity
from .const import CONF_TESLAMATE_CHARGE_LIMIT_ENTITY
from .seat_model import vehicle_unique_id
from .telemetry import TeslaMateStateMixin, numeric_state


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TeslaMate-backed charge limit."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            TeslaVirtualChargeLimit(
                runtime.vehicle,
                runtime.scopes,
                runtime.device_info,
                runtime.config[CONF_TESLAMATE_CHARGE_LIMIT_ENTITY],
            )
        ]
    )


class TeslaVirtualChargeLimit(
    TeslaMateStateMixin,
    TeslaCommandEntity,
    NumberEntity,
):
    """Charge-limit command using TeslaMate for the current value."""

    _attr_device_class = NumberDeviceClass.BATTERY
    _attr_has_entity_name = True
    _attr_mode = NumberMode.AUTO
    _attr_native_max_value = 100
    _attr_native_min_value = 50
    _attr_native_step = PRECISION_WHOLE
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        vehicle: Any,
        scopes: list[Scope],
        device_info: DeviceInfo,
        telemetry_entity_id: str,
    ) -> None:
        """Initialize the charge limit."""
        self._command_scope = (
            Scope.VEHICLE_CHARGING_CMDS
            if Scope.VEHICLE_CHARGING_CMDS in scopes
            else Scope.VEHICLE_CMDS
        )
        self.scoped = any(
            scope in scopes
            for scope in (Scope.VEHICLE_CHARGING_CMDS, Scope.VEHICLE_CMDS)
        )
        self._teslamate_entity_id = telemetry_entity_id
        super().__init__(vehicle, self.scoped)
        self._attr_device_info = device_info
        self._attr_translation_key = "charge_limit"
        self._attr_unique_id = vehicle_unique_id(
            "tesla_virtual_charge_limit",
            vehicle.vin,
        )
        self._attr_suggested_object_id = "tesla_charge_limit"

    def _update_from_teslamate_state(self, state: Any | None) -> None:
        """Set the current charge limit from TeslaMate."""
        self._attr_native_value = numeric_state(state)

    async def async_set_native_value(self, value: float) -> None:
        """Set the vehicle charge limit."""
        async with self._command_lock:
            limit = int(value)
            self.raise_for_read_only(self._command_scope)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.set_charge_limit(limit))
            self._attr_native_value = limit
            self.async_write_ha_state()
