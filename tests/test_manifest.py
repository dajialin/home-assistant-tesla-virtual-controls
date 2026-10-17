"""Manifest classification tests for the integrations dashboard."""

import json
import unittest
from pathlib import Path

COMPONENT = (
    Path(__file__).resolve().parents[1] / "custom_components" / "tesla_virtual_hvac"
)


class ManifestTests(unittest.TestCase):
    def test_single_vehicle_integration_is_classified_as_device(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["integration_type"],
            "device",
            "A vehicle config entry must appear in Integrations, not Helpers",
        )


if __name__ == "__main__":
    unittest.main()
