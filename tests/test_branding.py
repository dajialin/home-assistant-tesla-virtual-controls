"""Branding and compatibility tests for Tesla Virtual Controls."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components import tesla_virtual_hvac as integration
from custom_components.tesla_virtual_hvac.const import (
    CONF_FLEET_ENTITY,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    LEGACY_DEFAULT_MODEL,
    LEGACY_DEFAULT_NAME,
)

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "tesla_virtual_hvac"


class BrandingTests(unittest.TestCase):
    def test_public_name_and_compatibility_domain(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text())
        self.assertEqual(manifest["name"], "Tesla Virtual Controls")
        self.assertEqual(manifest["version"], "3.4.3")
        self.assertEqual(manifest["domain"], "tesla_virtual_hvac")
        self.assertEqual(DEFAULT_NAME, "Tesla Controls")
        self.assertEqual(DOMAIN, "tesla_virtual_hvac")

    def test_resources_do_not_expose_the_retired_name(self) -> None:
        resources = [
            COMPONENT / "strings.json",
            *sorted((COMPONENT / "translations").glob("*.json")),
        ]
        for path in resources:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("Tesla Virtual HVAC", text)
                self.assertNotIn("Tesla 虚拟 HVAC", text)
                self.assertNotIn("Tesla 虛擬 HVAC", text)
                data = json.loads(text)
                self.assertEqual(data["title"], "Tesla Virtual Controls")

    def test_legacy_default_name_is_migrated(self) -> None:
        entry = SimpleNamespace(
            data={
                "name": LEGACY_DEFAULT_NAME,
                CONF_FLEET_ENTITY: "climate.climate",
            },
            options={},
            title=LEGACY_DEFAULT_NAME,
        )
        hass = SimpleNamespace(config_entries=MagicMock())

        config = integration._migrate_legacy_display_name(hass, entry)

        self.assertEqual(config["name"], DEFAULT_NAME)
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry,
            data={
                "name": DEFAULT_NAME,
                CONF_FLEET_ENTITY: "climate.climate",
            },
            title=DEFAULT_NAME,
        )

    def test_custom_user_name_is_preserved(self) -> None:
        entry = SimpleNamespace(
            data={
                "name": "My Model 3",
                CONF_FLEET_ENTITY: "climate.climate",
            },
            options={},
            title="My Model 3",
        )
        hass = SimpleNamespace(config_entries=MagicMock())

        config = integration._migrate_legacy_display_name(hass, entry)

        self.assertEqual(config["name"], "My Model 3")
        hass.config_entries.async_update_entry.assert_not_called()

    def test_legacy_device_branding_is_migrated(self) -> None:
        registry = MagicMock()
        registry.async_get_device.return_value = SimpleNamespace(
            id="device-id",
            name=LEGACY_DEFAULT_NAME,
            model=LEGACY_DEFAULT_MODEL,
        )
        hass = SimpleNamespace()

        with patch.object(integration.dr, "async_get", return_value=registry):
            integration._migrate_legacy_device_branding(hass, "VIN123")

        registry.async_get_device.assert_called_once_with(
            identifiers={(DOMAIN, "VIN123")}
        )
        registry.async_update_device.assert_called_once_with(
            "device-id",
            name=DEFAULT_NAME,
            model=DEFAULT_MODEL,
        )


if __name__ == "__main__":
    unittest.main()
