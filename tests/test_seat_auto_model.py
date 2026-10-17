"""Automatic front-seat mode behavior."""

import unittest

from custom_components.tesla_virtual_hvac.seat_model import (
    SEAT_DEFINITIONS,
    SeatCommand,
    SeatFeature,
    front_option_from_levels,
    seat_command_plan,
)


class SeatAutoModelTests(unittest.TestCase):
    def test_front_definitions_map_auto_telemetry_and_api_positions(self) -> None:
        left, right = SEAT_DEFINITIONS[:2]
        self.assertEqual(left.auto, "climate_state_auto_seat_climate_left")
        self.assertEqual(left.auto_api_position, 1)
        self.assertEqual(right.auto, "climate_state_auto_seat_climate_right")
        self.assertEqual(right.auto_api_position, 2)

    def test_auto_telemetry_takes_precedence_over_manual_levels(self) -> None:
        self.assertEqual(front_option_from_levels(3, 0, True), "auto")
        self.assertEqual(front_option_from_levels(0, 2, True), "auto")
        self.assertEqual(front_option_from_levels(2, 0, False), "heat_medium")
        self.assertEqual(front_option_from_levels(0, 1, False), "ventilation_low")

    def test_auto_transition_disables_manual_modes_before_enabling_auto(self) -> None:
        front = SEAT_DEFINITIONS[0]
        self.assertEqual(
            seat_command_plan(front, "auto"),
            (
                SeatCommand(SeatFeature.HEATER, 0),
                SeatCommand(SeatFeature.VENTILATION, 0),
                SeatCommand(SeatFeature.AUTO, 1),
            ),
        )

    def test_manual_transition_disables_auto_and_opposite_mode_first(
        self,
    ) -> None:
        front = SEAT_DEFINITIONS[0]
        self.assertEqual(
            seat_command_plan(front, "heat_high"),
            (
                SeatCommand(SeatFeature.AUTO, 0),
                SeatCommand(SeatFeature.VENTILATION, 0),
                SeatCommand(SeatFeature.HEATER, 3),
            ),
        )
        self.assertEqual(
            seat_command_plan(front, "ventilation_medium"),
            (
                SeatCommand(SeatFeature.AUTO, 0),
                SeatCommand(SeatFeature.HEATER, 0),
                SeatCommand(SeatFeature.VENTILATION, 2),
            ),
        )

    def test_off_disables_auto_heating_and_ventilation(self) -> None:
        front = SEAT_DEFINITIONS[0]
        self.assertEqual(
            seat_command_plan(front, "off"),
            (
                SeatCommand(SeatFeature.AUTO, 0),
                SeatCommand(SeatFeature.HEATER, 0),
                SeatCommand(SeatFeature.VENTILATION, 0),
            ),
        )


if __name__ == "__main__":
    unittest.main()
