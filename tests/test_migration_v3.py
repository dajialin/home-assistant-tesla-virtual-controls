"""Config-entry migration to the four-seat model."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import custom_components.tesla_virtual_hvac as integration
from custom_components.tesla_virtual_hvac.config_flow import TeslaVirtualHvacConfigFlow
from custom_components.tesla_virtual_hvac.const import CONF_FLEET_ENTITY, DOMAIN


class FourSeatMigrationTests(unittest.TestCase):
    def test_v2_migration_removes_obsolete_rear_center_entity(self) -> None:
        registry = MagicMock()
        registry.async_get.return_value = SimpleNamespace(
            unique_id="VIN123-driver_temp"
        )
        registry.async_get_entity_id.return_value = (
            "select.tesla_virtual_seat_rear_center"
        )
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_update_entry=MagicMock())
        )
        entry = SimpleNamespace(
            version=2,
            data={CONF_FLEET_ENTITY: "climate.climate"},
            options={},
            entry_id="entry-1",
            unique_id="VIN123-driver_temp",
        )

        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(
                integration,
                "_remove_retired_comfort_entities",
            ) as remove_retired,
        ):
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        registry.async_get_entity_id.assert_called_with(
            "select",
            DOMAIN,
            "tesla_virtual_seat_rear_center_VIN123",
        )
        registry.async_remove.assert_called_once_with(
            "select.tesla_virtual_seat_rear_center"
        )
        remove_retired.assert_called_once_with(hass, "VIN123")
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry,
            version=4,
        )

    def test_v1_migration_preserves_front_and_removes_obsolete_entities(
        self,
    ) -> None:
        registry = MagicMock()
        registry.async_get.return_value = SimpleNamespace(
            unique_id="VIN123-driver_temp"
        )
        registry.async_get_entity_id.side_effect = [
            None,
            "select.tesla_virtual_seat_heater",
            "select.tesla_virtual_seat_ventilation",
            "select.tesla_virtual_seat_rear_center",
        ]
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_update_entry=MagicMock())
        )
        entry = SimpleNamespace(
            version=1,
            data={
                CONF_FLEET_ENTITY: "climate.climate",
                "seat_position": "front_right",
            },
            options={"seat_position": "front_right"},
            entry_id="entry-1",
            unique_id="VIN123-driver_temp",
        )

        with (
            patch.object(integration.er, "async_get", return_value=registry),
            patch.object(
                integration,
                "_remove_retired_comfort_entities",
            ) as remove_retired,
        ):
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        registry.async_update_entity.assert_called_once_with(
            "select.tesla_virtual_seat_heater",
            new_unique_id="tesla_virtual_seat_front_right_VIN123",
            config_entry_id="entry-1",
            has_entity_name=True,
            translation_key="seat_front_right",
        )
        self.assertEqual(
            registry.async_remove.call_args_list,
            [
                unittest.mock.call("select.tesla_virtual_seat_ventilation"),
                unittest.mock.call("select.tesla_virtual_seat_rear_center"),
            ],
        )
        remove_retired.assert_called_once_with(hass, "VIN123")
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry,
            data={CONF_FLEET_ENTITY: "climate.climate"},
            options={},
            version=4,
        )

    def test_new_config_entries_use_version_four(self) -> None:
        self.assertEqual(TeslaVirtualHvacConfigFlow.VERSION, 4)


if __name__ == "__main__":
    unittest.main()
