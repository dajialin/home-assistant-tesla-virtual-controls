"""Entity IDs use ordinary Tesla names and migrate in place."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from homeassistant.core import State
from homeassistant.exceptions import ConfigEntryError

import custom_components.tesla_virtual_hvac as integration
from custom_components.tesla_virtual_hvac.const import (
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    ENTITY_ID_TARGETS,
    LEGACY_ENTITY_IDS,
)
from custom_components.tesla_virtual_hvac.seat_model import vehicle_unique_id

EXPECTED_ENTITY_IDS = {
    "climate.tesla_climate",
    "cover.tesla_trunk",
    "cover.tesla_frunk",
    "cover.tesla_charge_port_door",
    "cover.tesla_windows",
    "switch.tesla_sentry_mode",
    "lock.tesla_vehicle",
    "number.tesla_charge_limit",
}


class EntityIdentityTests(unittest.TestCase):
    def test_default_device_branding_has_no_virtual_word(self) -> None:
        self.assertEqual(DEFAULT_NAME, "Tesla Controls")
        self.assertEqual(DEFAULT_MODEL, "Controls")
        self.assertNotIn("virtual", DEFAULT_NAME.lower())
        self.assertNotIn("virtual", DEFAULT_MODEL.lower())

    def test_all_target_entity_ids_are_ordinary_and_collision_free(self) -> None:
        self.assertEqual(set(ENTITY_ID_TARGETS.values()), EXPECTED_ENTITY_IDS)
        self.assertEqual(len(ENTITY_ID_TARGETS), 8)
        for entity_id in ENTITY_ID_TARGETS.values():
            with self.subTest(entity_id=entity_id):
                self.assertNotIn("virtual", entity_id)
                self.assertTrue(
                    entity_id.startswith(
                        tuple(
                            f"{domain}."
                            for domain in {
                                "climate",
                                "select",
                                "cover",
                                "switch",
                                "lock",
                                "number",
                            }
                        )
                    )
                )

    def test_registry_migration_keeps_unique_ids_and_changes_only_entity_ids(
        self,
    ) -> None:
        registry = MagicMock()
        current_ids = dict(LEGACY_ENTITY_IDS)

        def get_entity_id(platform: str, integration_domain: str, unique_id: str):
            self.assertEqual(integration_domain, DOMAIN)
            for base in ENTITY_ID_TARGETS:
                if unique_id == vehicle_unique_id(base, "VIN123"):
                    return current_ids[base]
            return None

        registry.async_get_entity_id.side_effect = get_entity_id
        registry.async_get.return_value = None
        hass = SimpleNamespace()
        first_base, first_target = next(iter(ENTITY_ID_TARGETS.items()))
        first_current = current_ids[first_base]
        stored_state = SimpleNamespace(state=State(first_current, "off"))
        restore_data = SimpleNamespace(last_states={first_current: stored_state})

        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(integration.rs, "async_get", return_value=restore_data),
        ):
            integration._migrate_entity_ids(hass, "VIN123")

        self.assertEqual(
            registry.async_update_entity.call_args_list,
            [
                call(current_ids[base], new_entity_id=target)
                for base, target in ENTITY_ID_TARGETS.items()
            ],
        )
        self.assertNotIn(first_current, restore_data.last_states)
        self.assertIs(restore_data.last_states[first_target], stored_state)
        self.assertEqual(stored_state.state.entity_id, first_target)

    def test_second_vehicle_uses_collision_free_suffix(self) -> None:
        registry = MagicMock()
        unique_id_base = "tesla_virtual_trunk"
        legacy_id = f"{LEGACY_ENTITY_IDS[unique_id_base]}_2"
        preferred = ENTITY_ID_TARGETS[unique_id_base]

        def get_entity_id(platform: str, integration_domain: str, unique_id: str):
            if unique_id == vehicle_unique_id(unique_id_base, "VIN456"):
                return legacy_id
            return None

        registry.async_get_entity_id.side_effect = get_entity_id
        registry.async_get.side_effect = lambda entity_id: (
            object() if entity_id == preferred else None
        )
        restore_data = SimpleNamespace(last_states={})
        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(integration.rs, "async_get", return_value=restore_data),
        ):
            integration._migrate_entity_ids(SimpleNamespace(), "VIN456")

        registry.async_update_entity.assert_called_once_with(
            legacy_id,
            new_entity_id=f"{preferred}_2",
        )

    def test_custom_entity_id_is_preserved(self) -> None:
        registry = MagicMock()
        registry.async_get_entity_id.side_effect = lambda platform, domain, unique_id: (
            "cover.my_custom_trunk"
            if unique_id == vehicle_unique_id("tesla_virtual_trunk", "VIN123")
            else None
        )
        restore_data = SimpleNamespace(last_states={})
        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(integration.rs, "async_get", return_value=restore_data),
        ):
            integration._migrate_entity_ids(SimpleNamespace(), "VIN123")

        registry.async_update_entity.assert_not_called()

    def test_command_only_mode_requires_fleet_polling_to_be_disabled(self) -> None:
        registry = MagicMock()
        registry.async_get.return_value = SimpleNamespace(
            config_entry_id="fleet-entry-id"
        )
        fleet_entry = SimpleNamespace(
            domain="tesla_fleet",
            pref_disable_polling=True,
        )
        config_entries = MagicMock()
        config_entries.async_get_entry.return_value = fleet_entry
        hass = SimpleNamespace(config_entries=config_entries)

        with patch.object(integration.er, "async_get", return_value=registry):
            integration._validate_fleet_polling_disabled(hass, "climate.climate")

        config_entries.async_update_entry.assert_not_called()

        fleet_entry.pref_disable_polling = False
        with (
            patch.object(integration.er, "async_get", return_value=registry),
            self.assertRaises(ConfigEntryError),
        ):
            integration._validate_fleet_polling_disabled(hass, "climate.climate")


if __name__ == "__main__":
    unittest.main()
