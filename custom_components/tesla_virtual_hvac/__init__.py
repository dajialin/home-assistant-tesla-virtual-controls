"""Tesla Virtual Controls integration."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.tesla_fleet.const import DOMAIN as TESLA_FLEET_DOMAIN
from homeassistant.components.tesla_fleet.models import TeslaFleetVehicleData
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import restore_state as rs
from homeassistant.helpers.device_registry import DeviceInfo
from tesla_fleet_api.const import Scope

from .const import (
    CONF_FLEET_ENTITY,
    CONF_SEAT_POSITION,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_UNIQUE_ID,
    DOMAIN,
    ENTITY_ID_TARGETS,
    LEGACY_DEFAULT_MODELS,
    LEGACY_DEFAULT_NAMES,
    LEGACY_ENTITY_IDS,
    PLATFORMS,
    RETIRED_COMFORT_UNIQUE_ID_BASES,
    TESLAMATE_TELEMETRY_DEFAULTS,
)
from .seat_model import SeatPosition, vehicle_unique_id


@dataclass(slots=True)
class TeslaVirtualHvacRuntimeData:
    """Resolved configuration and Tesla Fleet vehicle runtime."""

    config: dict[str, Any]
    vehicle: TeslaFleetVehicleData
    scopes: list[Scope]
    device_info: DeviceInfo
    climate_unique_id: str


def _migrate_legacy_display_name(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Rename only the former default while preserving custom user names."""
    data = dict(entry.data)
    options = dict(entry.options)
    update: dict[str, Any] = {}

    if data.get(CONF_NAME) in LEGACY_DEFAULT_NAMES:
        data[CONF_NAME] = DEFAULT_NAME
        update["data"] = data
    if options.get(CONF_NAME) in LEGACY_DEFAULT_NAMES:
        options[CONF_NAME] = DEFAULT_NAME
        update["options"] = options
    if entry.title in LEGACY_DEFAULT_NAMES:
        update["title"] = DEFAULT_NAME

    if update:
        hass.config_entries.async_update_entry(entry, **update)
    return {**TESLAMATE_TELEMETRY_DEFAULTS, **data, **options}


def _migrate_legacy_device_branding(hass: HomeAssistant, vin: str) -> None:
    """Rename the former default device label without changing identifiers."""
    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, vin)})
    if device is None:
        return

    update: dict[str, str] = {}
    if device.name in LEGACY_DEFAULT_NAMES:
        update["name"] = DEFAULT_NAME
    if device.model in LEGACY_DEFAULT_MODELS:
        update["model"] = DEFAULT_MODEL
    if update:
        registry.async_update_device(device.id, **update)


def _is_legacy_default_entity_id(current: str, legacy: str) -> bool:
    """Return whether Home Assistant generated this legacy ID automatically."""
    if current == legacy:
        return True
    suffix = current.removeprefix(f"{legacy}_")
    return current.startswith(f"{legacy}_") and suffix.isdigit() and int(suffix) >= 2


def _available_target_entity_id(
    registry: er.EntityRegistry,
    preferred: str,
) -> str:
    """Return the preferred ID or the first collision-free numeric suffix."""
    if registry.async_get(preferred) is None:
        return preferred
    index = 2
    while registry.async_get(candidate := f"{preferred}_{index}") is not None:
        index += 1
    return candidate


def _migrate_entity_ids(hass: HomeAssistant, vin: str) -> None:
    """Remove retired wording while preserving custom IDs and multiple VINs."""
    registry = er.async_get(hass)
    restore_data = rs.async_get(hass)
    for unique_id_base, preferred_entity_id in ENTITY_ID_TARGETS.items():
        platform = preferred_entity_id.split(".", maxsplit=1)[0]
        current_entity_id = registry.async_get_entity_id(
            platform,
            DOMAIN,
            vehicle_unique_id(unique_id_base, vin),
        )
        if current_entity_id is None or not _is_legacy_default_entity_id(
            current_entity_id,
            LEGACY_ENTITY_IDS[unique_id_base],
        ):
            continue
        target_entity_id = _available_target_entity_id(
            registry,
            preferred_entity_id,
        )
        registry.async_update_entity(
            current_entity_id,
            new_entity_id=target_entity_id,
        )
        if stored_state := restore_data.last_states.pop(current_entity_id, None):
            state = stored_state.state
            stored_state.state = State(
                target_entity_id,
                state.state,
                state.attributes,
                state.last_changed,
                state.last_reported,
                state.last_updated,
                state.context,
            )
            restore_data.last_states[target_entity_id] = stored_state


def _validate_fleet_polling_disabled(
    hass: HomeAssistant,
    fleet_entity_id: str,
) -> None:
    """Require the selected Fleet integration to stay command-only."""
    entity_entry = er.async_get(hass).async_get(fleet_entity_id)
    if entity_entry is None or entity_entry.config_entry_id is None:
        raise ConfigEntryNotReady(
            f"Tesla Fleet entity {fleet_entity_id} is not registered"
        )
    fleet_entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
    if fleet_entry is None or fleet_entry.domain != TESLA_FLEET_DOMAIN:
        raise ConfigEntryNotReady(
            f"Tesla Fleet config entry for {fleet_entity_id} is not ready"
        )
    if not fleet_entry.pref_disable_polling:
        raise ConfigEntryError(
            "Disable polling in the Tesla Fleet integration system options "
            "before loading Tesla Virtual Controls"
        )


def _resolve_vehicle(
    hass: HomeAssistant, fleet_entity_id: str
) -> tuple[TeslaFleetVehicleData, list[Scope]]:
    """Resolve a selected Tesla Fleet climate entity to its live vehicle runtime."""
    entity_entry = er.async_get(hass).async_get(fleet_entity_id)
    if entity_entry is None or entity_entry.config_entry_id is None:
        raise ConfigEntryNotReady(
            f"Tesla Fleet entity {fleet_entity_id} is not registered"
        )

    fleet_entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
    fleet_runtime = getattr(fleet_entry, "runtime_data", None)
    vehicles = getattr(fleet_runtime, "vehicles", None)
    if not vehicles:
        raise ConfigEntryNotReady("Tesla Fleet vehicle runtime is not ready")

    vin = entity_entry.unique_id.split("-", maxsplit=1)[0]
    for vehicle in vehicles:
        if vehicle.vin == vin:
            return vehicle, list(fleet_runtime.scopes)
    raise ConfigEntryNotReady(
        f"No Tesla Fleet vehicle runtime matches {fleet_entity_id}"
    )


def _migrate_legacy_climate_unique_id(
    hass: HomeAssistant,
    entry: ConfigEntry,
    new_unique_id: str,
) -> None:
    """Keep the existing climate entity ID while scoping its unique ID by VIN."""
    registry = er.async_get(hass)
    if existing_entity_id := registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        new_unique_id,
    ):
        existing_entry = registry.async_get(existing_entity_id)
        if existing_entry and existing_entry.config_entry_id != entry.entry_id:
            registry.async_update_entity(
                existing_entity_id,
                config_entry_id=entry.entry_id,
                has_entity_name=True,
                translation_key="driver_temp",
            )
        return
    legacy_entity_id = registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        DEFAULT_UNIQUE_ID,
    )
    if legacy_entity_id is not None:
        registry.async_update_entity(
            legacy_entity_id,
            new_unique_id=new_unique_id,
            config_entry_id=entry.entry_id,
            has_entity_name=True,
            translation_key="driver_temp",
        )


def _migrate_v1_seat_registry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    vin: str,
    position: SeatPosition,
) -> None:
    """Convert the former feature entities into one front-seat entity."""
    registry = er.async_get(hass)
    new_unique_id = vehicle_unique_id(
        f"tesla_virtual_seat_{position.value}",
        vin,
    )
    new_entity_id = registry.async_get_entity_id(
        SELECT_DOMAIN,
        DOMAIN,
        new_unique_id,
    )
    old_heater_id = registry.async_get_entity_id(
        SELECT_DOMAIN,
        DOMAIN,
        vehicle_unique_id("tesla_virtual_seat_heater", vin),
    )
    if new_entity_id is None and old_heater_id is not None:
        registry.async_update_entity(
            old_heater_id,
            new_unique_id=new_unique_id,
            config_entry_id=entry.entry_id,
            has_entity_name=True,
            translation_key=f"seat_{position.value}",
        )
    elif old_heater_id is not None and old_heater_id != new_entity_id:
        registry.async_remove(old_heater_id)

    old_ventilation_id = registry.async_get_entity_id(
        SELECT_DOMAIN,
        DOMAIN,
        vehicle_unique_id("tesla_virtual_seat_ventilation", vin),
    )
    if old_ventilation_id is not None:
        registry.async_remove(old_ventilation_id)


def _remove_rear_center_seat_registry(
    hass: HomeAssistant,
    vin: str,
) -> None:
    """Remove the obsolete virtual rear-center entity from the registry."""
    registry = er.async_get(hass)
    unique_id = vehicle_unique_id("tesla_virtual_seat_rear_center", vin)
    entity_id = registry.async_get_entity_id(
        SELECT_DOMAIN,
        DOMAIN,
        unique_id,
    )
    if entity_id is not None:
        registry.async_remove(entity_id)


def _remove_retired_comfort_entities(hass: HomeAssistant, vin: str) -> None:
    """Remove the retired custom seat and steering controls."""
    registry = er.async_get(hass)
    restore_data = rs.async_get(hass)
    for unique_id_base in RETIRED_COMFORT_UNIQUE_ID_BASES:
        entity_id = registry.async_get_entity_id(
            SELECT_DOMAIN,
            DOMAIN,
            vehicle_unique_id(unique_id_base, vin),
        )
        if entity_id is None:
            continue
        restore_data.last_states.pop(entity_id, None)
        registry.async_remove(entity_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy settings and remove retired comfort controls."""
    if entry.version > 4:
        return False
    if entry.version == 4:
        return True

    current = {**entry.data, **entry.options}
    registry_entry = er.async_get(hass).async_get(entry.data[CONF_FLEET_ENTITY])
    fleet_unique_id = getattr(registry_entry, "unique_id", None) or getattr(
        entry, "unique_id", None
    )
    vin = fleet_unique_id.split("-", maxsplit=1)[0] if fleet_unique_id else None

    update: dict[str, Any] = {"version": 4}
    if entry.version == 1:
        try:
            position = SeatPosition(
                current.get(CONF_SEAT_POSITION, SeatPosition.FRONT_RIGHT)
            )
        except ValueError:
            position = SeatPosition.FRONT_RIGHT

        if vin:
            _migrate_v1_seat_registry(hass, entry, vin, position)

        data = dict(entry.data)
        options = dict(entry.options)
        data.pop(CONF_SEAT_POSITION, None)
        options.pop(CONF_SEAT_POSITION, None)
        update.update(data=data, options=options)

    if vin:
        _remove_rear_center_seat_registry(hass, vin)
        _remove_retired_comfort_entities(hass, vin)

    hass.config_entries.async_update_entry(
        entry,
        **update,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tesla Virtual Controls from a Web UI config entry."""
    config = _migrate_legacy_display_name(hass, entry)
    _validate_fleet_polling_disabled(hass, config[CONF_FLEET_ENTITY])
    vehicle, scopes = _resolve_vehicle(hass, config[CONF_FLEET_ENTITY])
    _migrate_legacy_device_branding(hass, vehicle.vin)
    climate_unique_id = vehicle_unique_id(DEFAULT_UNIQUE_ID, vehicle.vin)
    _migrate_legacy_climate_unique_id(hass, entry, climate_unique_id)
    _migrate_entity_ids(hass, vehicle.vin)
    entry.runtime_data = TeslaVirtualHvacRuntimeData(
        config=config,
        vehicle=vehicle,
        scopes=scopes,
        device_info=DeviceInfo(
            identifiers={(DOMAIN, vehicle.vin)},
            name=config[CONF_NAME],
            manufacturer="Tesla",
            model=DEFAULT_MODEL,
            via_device=(TESLA_FLEET_DOMAIN, vehicle.vin),
        ),
        climate_unique_id=climate_unique_id,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Tesla Virtual Controls platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
