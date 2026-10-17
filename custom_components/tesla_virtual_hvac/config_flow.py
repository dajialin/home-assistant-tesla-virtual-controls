"""Config flow for Tesla Virtual Controls."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_FLEET_ENTITY,
    CONF_MQTT_CLIMATE_ON_ENTITY,
    CONF_MQTT_CURRENT_TEMPERATURE_ENTITY,
    CONF_MQTT_PRESET_ENTITY,
    CONF_TESLAMATE_CHARGE_LIMIT_ENTITY,
    CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY,
    CONF_TESLAMATE_FRUNK_ENTITY,
    CONF_TESLAMATE_LOCKED_ENTITY,
    CONF_TESLAMATE_SENTRY_MODE_ENTITY,
    CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
    CONF_TESLAMATE_TRUNK_ENTITY,
    CONF_TESLAMATE_WINDOWS_ENTITY,
    DEFAULT_FLEET_ENTITY,
    DEFAULT_MQTT_CLIMATE_ON_ENTITY,
    DEFAULT_MQTT_CURRENT_TEMPERATURE_ENTITY,
    DEFAULT_MQTT_PRESET_ENTITY,
    DEFAULT_NAME,
    DEFAULT_TESLAMATE_CHARGE_LIMIT_ENTITY,
    DEFAULT_TESLAMATE_CHARGE_PORT_DOOR_ENTITY,
    DEFAULT_TESLAMATE_FRUNK_ENTITY,
    DEFAULT_TESLAMATE_LOCKED_ENTITY,
    DEFAULT_TESLAMATE_SENTRY_MODE_ENTITY,
    DEFAULT_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
    DEFAULT_TESLAMATE_TRUNK_ENTITY,
    DEFAULT_TESLAMATE_WINDOWS_ENTITY,
    DOMAIN,
)


def _config_schema(
    defaults: Mapping[str, Any],
    *,
    fleet_read_only: bool = False,
) -> vol.Schema:
    """Build the user/options form with entity selectors."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=defaults.get(CONF_NAME, DEFAULT_NAME),
            ): selector.TextSelector(),
            vol.Required(
                CONF_FLEET_ENTITY,
                default=defaults.get(CONF_FLEET_ENTITY, DEFAULT_FLEET_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=CLIMATE_DOMAIN,
                    integration="tesla_fleet",
                    read_only=fleet_read_only,
                )
            ),
            vol.Required(
                CONF_MQTT_CLIMATE_ON_ENTITY,
                default=defaults.get(
                    CONF_MQTT_CLIMATE_ON_ENTITY,
                    DEFAULT_MQTT_CLIMATE_ON_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=BINARY_SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_MQTT_CURRENT_TEMPERATURE_ENTITY,
                default=defaults.get(
                    CONF_MQTT_CURRENT_TEMPERATURE_ENTITY,
                    DEFAULT_MQTT_CURRENT_TEMPERATURE_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
                default=defaults.get(
                    CONF_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
                    DEFAULT_TESLAMATE_TARGET_TEMPERATURE_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
            ),
            vol.Required(
                CONF_MQTT_PRESET_ENTITY,
                default=defaults.get(
                    CONF_MQTT_PRESET_ENTITY,
                    DEFAULT_MQTT_PRESET_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_TESLAMATE_TRUNK_ENTITY,
                default=defaults.get(
                    CONF_TESLAMATE_TRUNK_ENTITY,
                    DEFAULT_TESLAMATE_TRUNK_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=BINARY_SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_TESLAMATE_FRUNK_ENTITY,
                default=defaults.get(
                    CONF_TESLAMATE_FRUNK_ENTITY,
                    DEFAULT_TESLAMATE_FRUNK_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=BINARY_SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY,
                default=defaults.get(
                    CONF_TESLAMATE_CHARGE_PORT_DOOR_ENTITY,
                    DEFAULT_TESLAMATE_CHARGE_PORT_DOOR_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=BINARY_SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_TESLAMATE_WINDOWS_ENTITY,
                default=defaults.get(
                    CONF_TESLAMATE_WINDOWS_ENTITY,
                    DEFAULT_TESLAMATE_WINDOWS_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=BINARY_SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_TESLAMATE_LOCKED_ENTITY,
                default=defaults.get(
                    CONF_TESLAMATE_LOCKED_ENTITY,
                    DEFAULT_TESLAMATE_LOCKED_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=BINARY_SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_TESLAMATE_SENTRY_MODE_ENTITY,
                default=defaults.get(
                    CONF_TESLAMATE_SENTRY_MODE_ENTITY,
                    DEFAULT_TESLAMATE_SENTRY_MODE_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=BINARY_SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
            vol.Required(
                CONF_TESLAMATE_CHARGE_LIMIT_ENTITY,
                default=defaults.get(
                    CONF_TESLAMATE_CHARGE_LIMIT_ENTITY,
                    DEFAULT_TESLAMATE_CHARGE_LIMIT_ENTITY,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=SENSOR_DOMAIN,
                    integration="mqtt",
                )
            ),
        }
    )


def _fleet_unique_id(hass: HomeAssistant, entity_id: str) -> str:
    """Return the stable Tesla Fleet unique ID behind a selected climate entity."""
    entity_entry = er.async_get(hass).async_get(entity_id)
    if entity_entry is not None:
        return entity_entry.unique_id
    return entity_id


class TeslaVirtualHvacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Tesla Virtual Controls configuration."""

    VERSION = 4

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a Tesla Virtual Controls entry."""
        if user_input is not None:
            await self.async_set_unique_id(
                _fleet_unique_id(self.hass, user_input[CONF_FLEET_ENTITY])
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_config_schema({}),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import legacy YAML configuration into the Web UI."""
        await self.async_set_unique_id(
            _fleet_unique_id(self.hass, import_data[CONF_FLEET_ENTITY])
        )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data.get(CONF_NAME, DEFAULT_NAME),
            data=import_data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the Web UI options flow."""
        return TeslaVirtualHvacOptionsFlow()


class TeslaVirtualHvacOptionsFlow(OptionsFlowWithReload):
    """Edit Tesla Virtual Controls settings and reload the entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Tesla Virtual Controls options."""
        if user_input is not None:
            user_input[CONF_FLEET_ENTITY] = self.config_entry.data[CONF_FLEET_ENTITY]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                title=user_input[CONF_NAME],
            )
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        current[CONF_FLEET_ENTITY] = self.config_entry.data[CONF_FLEET_ENTITY]
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _config_schema(current, fleet_read_only=True),
                current,
            ),
        )
