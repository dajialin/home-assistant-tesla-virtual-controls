"""Tesla Virtual Controls climate platform."""

import asyncio
from datetime import datetime, timezone
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    PLATFORM_SCHEMA,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    PRECISION_HALVES,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_FLEET_ENTITY,
    CONF_MQTT_CLIMATE_ON_ENTITY,
    CONF_MQTT_CURRENT_TEMPERATURE_ENTITY,
    CONF_MQTT_PRESET_ENTITY,
    CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
    DEFAULT_FLEET_ENTITY,
    DEFAULT_MQTT_CLIMATE_ON_ENTITY,
    DEFAULT_MQTT_CURRENT_TEMPERATURE_ENTITY,
    DEFAULT_MQTT_PRESET_ENTITY,
    DEFAULT_NAME,
    DEFAULT_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
    DEFAULT_UNIQUE_ID,
    PRESET_MODES,
)
from .selector import TeslaHvacModel, TeslaHvacSnapshot, TimedValue

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID, default=DEFAULT_UNIQUE_ID): cv.string,
        vol.Optional(CONF_FLEET_ENTITY, default=DEFAULT_FLEET_ENTITY): cv.entity_id,
        vol.Optional(
            CONF_MQTT_CLIMATE_ON_ENTITY,
            default=DEFAULT_MQTT_CLIMATE_ON_ENTITY,
        ): cv.entity_id,
        vol.Optional(
            CONF_MQTT_CURRENT_TEMPERATURE_ENTITY,
            default=DEFAULT_MQTT_CURRENT_TEMPERATURE_ENTITY,
        ): cv.entity_id,
        vol.Optional(
            CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
            default=DEFAULT_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
        ): cv.entity_id,
        vol.Optional(
            CONF_MQTT_PRESET_ENTITY,
            default=DEFAULT_MQTT_PRESET_ENTITY,
        ): cv.entity_id,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tesla Virtual Controls YAML platform."""
    async_add_entities([TeslaVirtualHvac(config)])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tesla Virtual Controls Web UI config entry."""
    runtime = entry.runtime_data
    config = {**runtime.config, CONF_UNIQUE_ID: runtime.climate_unique_id}
    async_add_entities([TeslaVirtualHvac(config, device_info=runtime.device_info)])


class TeslaVirtualHvac(ClimateEntity):
    """A TeslaMate state facade that sends commands through Tesla Fleet."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "driver_temp"
    _attr_suggested_object_id = "tesla_climate"
    _attr_icon = "mdi:car-defrost-front"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_min_temp = 15
    _attr_max_temp = 28
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    ]
    _attr_preset_modes: ClassVar[list[str]] = PRESET_MODES
    _attr_hvac_mode: HVACMode | None = None
    _attr_current_temperature: float | None = None
    _attr_target_temperature: float | None = None
    _attr_preset_mode: str | None = None
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        config: ConfigType,
        *,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the virtual HVAC entity."""
        self._attr_unique_id = config.get(CONF_UNIQUE_ID, DEFAULT_UNIQUE_ID)
        if device_info is not None:
            self._attr_device_info = device_info
        self._fleet_entity = config[CONF_FLEET_ENTITY]
        self._mqtt_climate_on_entity = config[CONF_MQTT_CLIMATE_ON_ENTITY]
        self._mqtt_current_temperature_entity = config[
            CONF_MQTT_CURRENT_TEMPERATURE_ENTITY
        ]
        self._teslamate_target_temperature_entity = config[
            CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY
        ]
        self._mqtt_preset_entity = config[CONF_MQTT_PRESET_ENTITY]
        self._source_entities = {
            self._mqtt_climate_on_entity,
            self._mqtt_current_temperature_entity,
            self._teslamate_target_temperature_entity,
            self._mqtt_preset_entity,
        }
        self._model = TeslaHvacModel()
        self._command_lock = asyncio.Lock()
        self._optimistic: dict[str, TimedValue[Any]] = {}
        self._snapshot = self._model.snapshot()

    async def async_added_to_hass(self) -> None:
        """Subscribe to every live source without polling the vehicle."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._source_entities,
                self._async_source_changed,
            )
        )
        for entity_id in self._source_entities:
            if state := self.hass.states.get(entity_id):
                self._observe_state(state)
        self._apply_snapshot()

    @callback
    def _async_source_changed(self, event: Event) -> None:
        """Apply only fields whose relevant source value actually changed."""
        if (state := event.data.get("new_state")) is None:
            return
        if field := self._observe_state(state):
            self._optimistic.pop(field, None)
        self._apply_snapshot()
        self.async_write_ha_state()

    @callback
    def _observe_state(self, state: State) -> str | None:
        """Feed one Home Assistant source state into the per-field model."""
        entity_id = state.entity_id
        if entity_id == self._mqtt_climate_on_entity:
            changed = self._model.observe_mqtt_hvac(state.state, state.last_changed)
            return "hvac_mode" if changed else None
        elif entity_id == self._mqtt_current_temperature_entity:
            changed = self._model.observe_mqtt_current_temperature(
                state.state, state.last_changed
            )
            return "current_temperature" if changed else None
        elif entity_id == self._teslamate_target_temperature_entity:
            changed = self._model.observe_teslamate_target_temperature(
                state.state, state.last_changed
            )
            return "target_temperature" if changed else None
        elif entity_id == self._mqtt_preset_entity:
            changed = self._model.observe_mqtt_preset(state.state, state.last_changed)
            return "preset_mode" if changed else None
        return None

    @callback
    def _apply_snapshot(self) -> None:
        """Expose source values with independent optimistic command overlays."""
        source = self._model.snapshot()
        self._snapshot = TeslaHvacSnapshot(
            hvac_mode=self._optimistic.get("hvac_mode", source.hvac_mode),
            current_temperature=source.current_temperature,
            target_temperature=self._optimistic.get(
                "target_temperature", source.target_temperature
            ),
            preset_mode=self._optimistic.get("preset_mode", source.preset_mode),
        )
        if self._snapshot.hvac_mode:
            self._attr_hvac_mode = HVACMode(self._snapshot.hvac_mode.value)
        if self._snapshot.current_temperature:
            self._attr_current_temperature = self._snapshot.current_temperature.value
        if self._snapshot.target_temperature:
            self._attr_target_temperature = self._snapshot.target_temperature.value
        if self._snapshot.preset_mode:
            self._attr_preset_mode = self._snapshot.preset_mode.value

    @callback
    def _set_optimistic(self, **values: Any) -> None:
        """Publish successful command values until their source fields change."""
        changed_at = datetime.now(timezone.utc)
        for field, value in values.items():
            self._optimistic[field] = TimedValue("command", value, changed_at)
        self._apply_snapshot()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose the winning source and timestamp for auditability."""
        attributes: dict[str, str] = {}
        for field, sample in (
            ("hvac_mode", self._snapshot.hvac_mode),
            ("current_temperature", self._snapshot.current_temperature),
            ("target_temperature", self._snapshot.target_temperature),
            ("preset_mode", self._snapshot.preset_mode),
        ):
            if sample:
                self._add_source_attributes(attributes, field, sample)
        return attributes

    @staticmethod
    def _add_source_attributes(
        attributes: dict[str, str], field: str, sample: TimedValue[Any]
    ) -> None:
        """Add one field's winning source metadata."""
        attributes[f"{field}_source"] = sample.source
        attributes[f"{field}_source_changed_at"] = sample.changed_at.isoformat()

    async def _async_call_fleet(self, service: str, data: dict[str, Any]) -> None:
        """Forward a control command directly to the Tesla Fleet climate entity."""
        await self.hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._fleet_entity, **data},
            blocking=True,
            context=self._context,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set Tesla HVAC mode directly."""
        async with self._command_lock:
            await self._async_call_fleet(
                SERVICE_SET_HVAC_MODE,
                {ATTR_HVAC_MODE: hvac_mode},
            )
            values: dict[str, Any] = {"hvac_mode": hvac_mode.value}
            if hvac_mode == HVACMode.OFF:
                values["preset_mode"] = PRESET_MODES[0]
            self._set_optimistic(**values)

    async def async_turn_on(self) -> None:
        """Turn Tesla HVAC on."""
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    async def async_turn_off(self) -> None:
        """Turn Tesla HVAC off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set Tesla target temperature directly."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        async with self._command_lock:
            await self._async_call_fleet(
                SERVICE_SET_TEMPERATURE,
                {ATTR_TEMPERATURE: temperature},
            )
            self._set_optimistic(target_temperature=temperature)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set Tesla climate keeper mode directly."""
        async with self._command_lock:
            await self._async_call_fleet(
                SERVICE_SET_PRESET_MODE,
                {ATTR_PRESET_MODE: preset_mode},
            )
            values: dict[str, Any] = {"preset_mode": preset_mode}
            if preset_mode != PRESET_MODES[0]:
                values["hvac_mode"] = HVACMode.HEAT_COOL.value
            self._set_optimistic(**values)
