"""TeslaMate-state vehicle covers with Tesla Fleet command execution."""

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.tesla_fleet.helpers import handle_vehicle_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from tesla_fleet_api.const import Scope, Trunk, WindowCommand

from .command import TeslaCommandEntity
from .const import (
    CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY,
    CONF_TESLAMATE_FRUNK_ENTITY,
    CONF_TESLAMATE_TRUNK_ENTITY,
    CONF_TESLAMATE_WINDOWS_ENTITY,
    DOMAIN,
)
from .seat_model import vehicle_unique_id
from .telemetry import TeslaMateStateMixin, binary_state


def _raise_if_toggle_state_unknown(entity: TeslaMateStateMixin) -> None:
    """Fail closed when a toggle command cannot determine current state."""
    if entity.is_closed is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="telemetry_unavailable",
            translation_placeholders={"entity_id": entity.telemetry_entity_id},
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TeslaMate-backed covers."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            TeslaVirtualRearTrunk(
                runtime.vehicle,
                Scope.VEHICLE_CMDS in runtime.scopes,
                runtime.device_info,
                runtime.config[CONF_TESLAMATE_TRUNK_ENTITY],
            ),
            TeslaVirtualFrontTrunk(
                runtime.vehicle,
                Scope.VEHICLE_CMDS in runtime.scopes,
                runtime.device_info,
                runtime.config[CONF_TESLAMATE_FRUNK_ENTITY],
            ),
            TeslaVirtualChargePortDoor(
                runtime.vehicle,
                runtime.scopes,
                runtime.device_info,
                runtime.config[CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY],
            ),
            TeslaVirtualWindows(
                runtime.vehicle,
                Scope.VEHICLE_CMDS in runtime.scopes,
                runtime.device_info,
                runtime.config[CONF_TESLAMATE_WINDOWS_ENTITY],
            ),
        ]
    )


class TeslaVirtualWindows(TeslaMateStateMixin, TeslaCommandEntity, CoverEntity):
    """Vent and close all windows using TeslaMate for status."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_has_entity_name = True
    _attr_is_closed: bool | None = None

    def __init__(
        self,
        vehicle: Any,
        scoped: bool,
        device_info: DeviceInfo,
        telemetry_entity_id: str,
    ) -> None:
        """Initialize the windows cover."""
        self.scoped = scoped
        self._teslamate_entity_id = telemetry_entity_id
        super().__init__(vehicle, scoped)
        self._attr_device_info = device_info
        self._attr_translation_key = "windows"
        self._attr_unique_id = vehicle_unique_id(
            "tesla_virtual_windows",
            vehicle.vin,
        )
        self._attr_suggested_object_id = "tesla_windows"
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
            if scoped
            else CoverEntityFeature(0)
        )

    def _update_from_teslamate_state(self, state: Any | None) -> None:
        """Set state from TeslaMate's aggregate windows-open sensor."""
        value = binary_state(state)
        self._attr_is_closed = None if value is None else not value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Vent all windows."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(
                self.api.window_control(command=WindowCommand.VENT)
            )
            self._attr_is_closed = False
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close all windows."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(
                self.api.window_control(command=WindowCommand.CLOSE)
            )
            self._attr_is_closed = True
            self.async_write_ha_state()


class TeslaVirtualChargePortDoor(
    TeslaMateStateMixin,
    TeslaCommandEntity,
    CoverEntity,
):
    """Control the charge-port door using TeslaMate for status."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_has_entity_name = True
    _attr_is_closed: bool | None = None

    def __init__(
        self,
        vehicle: Any,
        scopes: list[Scope],
        device_info: DeviceInfo,
        telemetry_entity_id: str,
    ) -> None:
        """Initialize the charge-port door."""
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
        self._attr_translation_key = "charge_port_door"
        self._attr_unique_id = vehicle_unique_id(
            "tesla_virtual_charge_port_door",
            vehicle.vin,
        )
        self._attr_suggested_object_id = "tesla_charge_port_door"
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
            if self.scoped
            else CoverEntityFeature(0)
        )

    def _update_from_teslamate_state(self, state: Any | None) -> None:
        """Set charge-port state from TeslaMate."""
        value = binary_state(state)
        self._attr_is_closed = None if value is None else not value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the charge-port door."""
        async with self._command_lock:
            self.raise_for_read_only(self._command_scope)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.charge_port_door_open())
            self._attr_is_closed = False
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the charge-port door."""
        async with self._command_lock:
            self.raise_for_read_only(self._command_scope)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.charge_port_door_close())
            self._attr_is_closed = True
            self.async_write_ha_state()


class TeslaVirtualFrontTrunk(
    TeslaMateStateMixin,
    TeslaCommandEntity,
    CoverEntity,
):
    """Open-only front trunk using TeslaMate for status."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_has_entity_name = True
    _attr_is_closed: bool | None = None

    def __init__(
        self,
        vehicle: Any,
        scoped: bool,
        device_info: DeviceInfo,
        telemetry_entity_id: str,
    ) -> None:
        """Initialize the front trunk."""
        self.scoped = scoped
        self._teslamate_entity_id = telemetry_entity_id
        super().__init__(vehicle, scoped)
        self._attr_device_info = device_info
        self._attr_translation_key = "frunk"
        self._attr_unique_id = vehicle_unique_id(
            "tesla_virtual_frunk",
            vehicle.vin,
        )
        self._attr_suggested_object_id = "tesla_frunk"
        self._attr_supported_features = (
            CoverEntityFeature.OPEN if scoped else CoverEntityFeature(0)
        )

    def _update_from_teslamate_state(self, state: Any | None) -> None:
        """Set front-trunk state from TeslaMate."""
        value = binary_state(state)
        self._attr_is_closed = None if value is None else not value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the front trunk when it is not already open."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            _raise_if_toggle_state_unknown(self)
            if self.is_closed is not False:
                await self.wake_up_if_asleep()
                _raise_if_toggle_state_unknown(self)
                if self.is_closed is not False:
                    await handle_vehicle_command(self.api.actuate_trunk(Trunk.FRONT))
                    self._attr_is_closed = False
                    self.async_write_ha_state()


class TeslaVirtualRearTrunk(
    TeslaMateStateMixin,
    TeslaCommandEntity,
    CoverEntity,
):
    """Powered rear trunk using TeslaMate for status."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_has_entity_name = True
    _attr_is_closed: bool | None = None

    def __init__(
        self,
        vehicle: Any,
        scoped: bool,
        device_info: DeviceInfo,
        telemetry_entity_id: str,
    ) -> None:
        """Initialize the rear trunk."""
        self.scoped = scoped
        self._teslamate_entity_id = telemetry_entity_id
        super().__init__(vehicle, scoped)
        self._attr_device_info = device_info
        self._attr_translation_key = "trunk"
        self._attr_unique_id = vehicle_unique_id(
            "tesla_virtual_trunk",
            vehicle.vin,
        )
        self._attr_suggested_object_id = "tesla_trunk"
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
            if scoped
            else CoverEntityFeature(0)
        )

    def _update_from_teslamate_state(self, state: Any | None) -> None:
        """Set rear-trunk state from TeslaMate."""
        value = binary_state(state)
        self._attr_is_closed = None if value is None else not value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the rear trunk when it is not already open."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            _raise_if_toggle_state_unknown(self)
            if self.is_closed is not False:
                await self.wake_up_if_asleep()
                _raise_if_toggle_state_unknown(self)
                if self.is_closed is not False:
                    await handle_vehicle_command(self.api.actuate_trunk(Trunk.REAR))
                    self._attr_is_closed = False
                    self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the rear trunk when it is not already closed."""
        async with self._command_lock:
            self.raise_for_read_only(Scope.VEHICLE_CMDS)
            _raise_if_toggle_state_unknown(self)
            if self.is_closed is not True:
                await self.wake_up_if_asleep()
                _raise_if_toggle_state_unknown(self)
                if self.is_closed is not True:
                    await handle_vehicle_command(self.api.actuate_trunk(Trunk.REAR))
                    self._attr_is_closed = True
                    self.async_write_ha_state()
