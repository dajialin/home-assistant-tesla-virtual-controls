"""Removal migration for retired seat and steering controls."""

import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from homeassistant.const import Platform

import custom_components.tesla_virtual_hvac as integration
from custom_components.tesla_virtual_hvac.config_flow import TeslaVirtualHvacConfigFlow
from custom_components.tesla_virtual_hvac.const import (
    CONF_FLEET_ENTITY,
    DOMAIN,
    ENTITY_ID_TARGETS,
    PLATFORMS,
)

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "tesla_virtual_hvac"
RETIRED_UNIQUE_ID_BASES = (
    "tesla_virtual_seat_front_left",
    "tesla_virtual_seat_front_right",
    "tesla_virtual_seat_rear_left",
    "tesla_virtual_seat_rear_right",
    "tesla_virtual_steering_wheel_heater",
)


class ComfortControlRemovalTests(unittest.TestCase):
    def test_select_platform_and_public_targets_are_removed(self) -> None:
        self.assertEqual(
            PLATFORMS,
            [
                Platform.CLIMATE,
                Platform.COVER,
                Platform.SWITCH,
                Platform.LOCK,
                Platform.NUMBER,
            ],
        )
        self.assertFalse(
            any(
                "seat" in target or "steering" in target
                for target in ENTITY_ID_TARGETS.values()
            )
        )

    def test_version_four_migration_removes_registry_and_restore_state(self) -> None:
        remove_retired = getattr(
            integration,
            "_remove_retired_comfort_entities",
            None,
        )
        self.assertIsNotNone(remove_retired)
        assert remove_retired is not None

        entity_ids = {
            base: f"select.custom_{index}"
            for index, base in enumerate(RETIRED_UNIQUE_ID_BASES, start=1)
        }
        registry = MagicMock()
        registry.async_get_entity_id.side_effect = lambda platform, domain, unique_id: (
            next(
                (
                    entity_id
                    for base, entity_id in entity_ids.items()
                    if unique_id == f"{base}_VIN123"
                ),
                None,
            )
        )
        restore_data = SimpleNamespace(
            last_states={entity_id: object() for entity_id in entity_ids.values()}
        )

        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(integration.rs, "async_get", return_value=restore_data),
        ):
            remove_retired(SimpleNamespace(), "VIN123")

        self.assertEqual(
            registry.async_remove.call_args_list,
            [call(entity_id) for entity_id in entity_ids.values()],
        )
        self.assertEqual(restore_data.last_states, {})

    def test_new_entries_and_resources_have_no_select_entities(self) -> None:
        self.assertEqual(TeslaVirtualHvacConfigFlow.VERSION, 4)
        resources = [
            COMPONENT / "strings.json",
            COMPONENT / "icons.json",
            *sorted((COMPONENT / "translations").glob("*.json")),
        ]
        for path in resources:
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertNotIn("select", data["entity"])

    def test_version_three_entry_migrates_to_version_four(self) -> None:
        registry = MagicMock()
        registry.async_get.return_value = SimpleNamespace(
            unique_id="VIN123-driver_temp"
        )
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_update_entry=MagicMock())
        )
        entry = SimpleNamespace(
            version=3,
            data={CONF_FLEET_ENTITY: "climate.climate"},
            options={},
            entry_id="entry-1",
            unique_id="VIN123-driver_temp",
        )

        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(integration, "_remove_rear_center_seat_registry"),
            patch.object(
                integration,
                "_remove_retired_comfort_entities",
            ) as remove_retired,
        ):
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        remove_retired.assert_called_once_with(hass, "VIN123")
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry,
            version=4,
        )

    def test_removal_targets_only_this_custom_integration(self) -> None:
        registry = MagicMock()
        registry.async_get_entity_id.return_value = None
        restore_data = SimpleNamespace(last_states={})
        remove_retired = getattr(
            integration,
            "_remove_retired_comfort_entities",
            None,
        )
        self.assertIsNotNone(remove_retired)
        assert remove_retired is not None

        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(integration.rs, "async_get", return_value=restore_data),
        ):
            remove_retired(SimpleNamespace(), "VIN123")

        for args, kwargs in registry.async_get_entity_id.call_args_list:
            self.assertEqual(args[0], Platform.SELECT)
            self.assertEqual(args[1], DOMAIN)
            self.assertEqual(kwargs, {})
        registry.async_remove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
