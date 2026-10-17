"""Translations, icons, platforms, and version resources."""

import json
import unittest
from pathlib import Path

from homeassistant.const import Platform

from custom_components.tesla_virtual_hvac.const import PLATFORMS

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "tesla_virtual_hvac"
EXPECTED_CONTROLS = {
    "cover": {"trunk", "frunk", "charge_port_door", "windows"},
    "switch": {"sentry_mode"},
    "lock": {"vehicle_lock"},
    "number": {"charge_limit"},
}
EXPECTED_TELEMETRY_FIELDS = {
    "teslamate_trunk_entity",
    "teslamate_frunk_entity",
    "teslamate_charge_port_door_entity",
    "teslamate_windows_entity",
    "teslamate_locked_entity",
    "teslamate_sentry_mode_entity",
    "teslamate_charge_limit_entity",
}


class ResourceTests(unittest.TestCase):
    def test_all_translation_files_match_entity_contract(self) -> None:
        resources = [
            COMPONENT / "strings.json",
            *sorted((COMPONENT / "translations").glob("*.json")),
        ]
        self.assertGreater(len(resources), 1)
        for path in resources:
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertNotIn("select", data["entity"])
                for domain, expected in EXPECTED_CONTROLS.items():
                    self.assertEqual(set(data["entity"][domain]), expected)
                self.assertTrue(
                    set(data["config"]["step"]["user"]["data"])
                    >= EXPECTED_TELEMETRY_FIELDS
                )
                self.assertTrue(
                    set(data["options"]["step"]["init"]["data"])
                    >= EXPECTED_TELEMETRY_FIELDS
                )
                self.assertIn("telemetry_unavailable", data["exceptions"])

    def test_icons_cover_all_active_controls(self) -> None:
        data = json.loads((COMPONENT / "icons.json").read_text(encoding="utf-8"))
        self.assertNotIn("select", data["entity"])
        for domain, expected in EXPECTED_CONTROLS.items():
            self.assertEqual(set(data["entity"][domain]), expected)
        for key in ("trunk", "frunk", "charge_port_door", "windows"):
            with self.subTest(key=key):
                icon = data["entity"]["cover"][key]
                self.assertIn("closed", icon["state"])
                self.assertNotEqual(icon["default"], icon["state"]["closed"])

    def test_chinese_and_japanese_entity_names_are_localized(self) -> None:
        simplified = json.loads(
            (COMPONENT / "translations" / "zh-Hans.json").read_text()
        )
        japanese = json.loads((COMPONENT / "translations" / "ja.json").read_text())
        self.assertEqual(
            simplified["entity"]["climate"]["driver_temp"]["name"],
            "空调",
        )
        self.assertEqual(
            simplified["entity"]["cover"]["charge_port_door"]["name"],
            "充电口盖",
        )
        self.assertEqual(
            simplified["entity"]["cover"]["windows"]["name"],
            "车窗",
        )
        self.assertEqual(
            simplified["entity"]["lock"]["vehicle_lock"]["name"],
            "车锁",
        )
        self.assertEqual(
            japanese["entity"]["cover"]["windows"]["name"],
            "ウィンドウ",
        )
        self.assertNotEqual(
            simplified["config"]["abort"]["already_configured"],
            "This Tesla Fleet climate entity is already configured.",
        )
        self.assertIn(
            "誤った切り替え",
            japanese["exceptions"]["telemetry_unavailable"]["message"],
        )

    def test_all_required_platforms_are_forwarded(self) -> None:
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

    def test_manifest_uses_current_release_version(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "3.4.3")

    def test_readme_states_the_quota_saving_architecture(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("TeslaMate telemetry", readme)
        self.assertIn("Tesla Fleet commands", readme)
        self.assertIn("API quota", readme)
        self.assertIn("temporary optimistic state", readme)
        self.assertIn("serialized per entity", readme)


if __name__ == "__main__":
    unittest.main()
