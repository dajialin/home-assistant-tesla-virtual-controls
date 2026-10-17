"""TeslaMate-state vehicle lock with Tesla Fleet command execution."""

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.components.tesla_fleet.helpers import handle_vehicle_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from tesla_fleet_api.const import Scope

from .command import TeslaCommandEntity
from .const import CONF_TESLAMATE_LOCKED_ENTITY
from .seat_model import vehicle_unique_id
from .telemetry import TeslaMateStateMixin, binary_state


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TeslaMate-backed vehicle lock."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            TeslaVirtualVehicleLock(
                runtime.vehicle,
                Scope.VEHICLE_CMDS in runtime.scopes,
                runtime.device_info,
                runtime.config[CONF_TESLAMATE_LOCKED_ENTITY],
            )
        ]
    )


class TeslaVirtualVehicleLock(
    TeslaMateStateMixin,
    TeslaCommandEntity,
    LockEntity,
):
    """Vehicle lock commands using TeslaMate for status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        vehicle: Any,
        scoped: bool,
        device_info: DeviceInfo,
        telemetry_entity_id: str,
    ) -> None:
        """Initialize the vehicle lock."""
        self.scoped = scoped
        self._teslamate_entity_id = telemetry_entity_id
        super().__init__(vehicle, scoped)
        self._attr_device_info = device_info
        self._attr_translation_key = "vehicle_lock"
        self._attr_unique_id = vehicle_unique_id(
            "tesla_virtual_vehicle_lock",
            vehicle.vin,
        )
        self._attr_suggested_object_id = "tesla_vehicle"

    def _update_from_teslamate_state(self, state: Any | None) -> None:
        """Set lock state from TeslaMate's lock-class binary sensor."""
        unlocked = binary_state(state)
        self._attr_is_locked = None if unlocked is None else not unlocked

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock all vehicle doors."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.door_lock())
            self._attr_is_locked = True
            self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock all vehicle doors."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.door_unlock())
            self._attr_is_locked = False
            self.async_write_ha_state()
