"""Seat shape and option requirements for Tesla Virtual HVAC."""

import unittest

from custom_components.tesla_virtual_hvac.seat_model import (
    FRONT_SEAT_OPTIONS,
    REAR_SEAT_OPTIONS,
    SEAT_DEFINITIONS,
    SeatPosition,
)


class SeatShapeTests(unittest.TestCase):
    def test_model_3_has_exactly_four_controllable_seat_entities(self) -> None:
        self.assertEqual(
            [definition.position for definition in SEAT_DEFINITIONS],
            [
                SeatPosition.FRONT_LEFT,
                SeatPosition.FRONT_RIGHT,
                SeatPosition.REAR_LEFT,
                SeatPosition.REAR_RIGHT,
            ],
        )

    def test_front_seats_include_auto_and_manual_comfort_modes(self) -> None:
        self.assertEqual(
            FRONT_SEAT_OPTIONS,
            [
                "off",
                "auto",
                "heat_low",
                "heat_medium",
                "heat_high",
                "ventilation_low",
                "ventilation_medium",
                "ventilation_high",
            ],
        )
        for definition in SEAT_DEFINITIONS[:2]:
            self.assertEqual(definition.options, FRONT_SEAT_OPTIONS)

    def test_rear_seats_are_heater_only_without_auto(self) -> None:
        self.assertEqual(REAR_SEAT_OPTIONS, ["off", "low", "medium", "high"])
        for definition in SEAT_DEFINITIONS[2:]:
            self.assertIsNone(definition.ventilation)
            self.assertEqual(definition.options, REAR_SEAT_OPTIONS)
            self.assertNotIn("auto", definition.options)


if __name__ == "__main__":
    unittest.main()
