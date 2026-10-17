"""TeslaMate-state switches with Tesla Fleet command execution."""

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.components.tesla_fleet.helpers import handle_vehicle_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from tesla_fleet_api.const import Scope

from .command import TeslaCommandEntity
from .const import CONF_TESLAMATE_SENTRY_MODE_ENTITY
from .seat_model import vehicle_unique_id
from .telemetry import TeslaMateStateMixin, binary_state


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TeslaMate-backed switches."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            TeslaVirtualSentryMode(
                runtime.vehicle,
                Scope.VEHICLE_CMDS in runtime.scopes,
                runtime.device_info,
                runtime.config[CONF_TESLAMATE_SENTRY_MODE_ENTITY],
            )
        ]
    )


class TeslaVirtualSentryMode(
    TeslaMateStateMixin,
    TeslaCommandEntity,
    SwitchEntity,
):
    """Sentry-mode command switch using TeslaMate for status."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_has_entity_name = True

    def __init__(
        self,
        vehicle: Any,
        scoped: bool,
        device_info: DeviceInfo,
        telemetry_entity_id: str,
    ) -> None:
        """Initialize sentry mode."""
        self.scoped = scoped
        self._teslamate_entity_id = telemetry_entity_id
        super().__init__(vehicle, scoped)
        self._attr_device_info = device_info
        self._attr_translation_key = "sentry_mode"
        self._attr_unique_id = vehicle_unique_id(
            "tesla_virtual_sentry_mode",
            vehicle.vin,
        )
        self._attr_suggested_object_id = "tesla_sentry_mode"

    def _update_from_teslamate_state(self, state: Any | None) -> None:
        """Set sentry mode from TeslaMate."""
        self._attr_is_on = binary_state(state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable sentry mode."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.set_sentry_mode(on=True))
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable sentry mode."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.set_sentry_mode(on=False))
            self._attr_is_on = False
            self.async_write_ha_state()
