"""Pure four-seat control mappings for Tesla Virtual Controls."""

from dataclasses import dataclass
from enum import StrEnum

FRONT_SEAT_OPTIONS = [
    "off",
    "auto",
    "heat_low",
    "heat_medium",
    "heat_high",
    "ventilation_low",
    "ventilation_medium",
    "ventilation_high",
]
REAR_SEAT_OPTIONS = ["off", "low", "medium", "high"]
_LEVEL_NAMES = ["off", "low", "medium", "high"]


def vehicle_unique_id(base: str, vin: str) -> str:
    """Scope a config-entry entity unique ID to one Tesla vehicle."""
    return f"{base}_{vin}"


class SeatPosition(StrEnum):
    """The four controllable seat positions in this Tesla Model 3."""

    FRONT_LEFT = "front_left"
    FRONT_RIGHT = "front_right"
    REAR_LEFT = "rear_left"
    REAR_RIGHT = "rear_right"


class SeatFeature(StrEnum):
    """A remotely controllable seat comfort feature."""

    AUTO = "auto"
    HEATER = "heater"
    VENTILATION = "ventilation"


@dataclass(frozen=True, slots=True)
class SeatDefinition:
    """Coordinator keys, API position, and presentation for one seat."""

    position: SeatPosition
    translation_key: str
    heater: str
    api_position: int
    ventilation: str | None = None
    auto: str | None = None
    auto_api_position: int | None = None

    @property
    def options(self) -> list[str]:
        """Return the options supported by this seat."""
        return FRONT_SEAT_OPTIONS if self.ventilation else REAR_SEAT_OPTIONS


@dataclass(frozen=True, slots=True)
class SeatCommand:
    """One command in an atomic seat-mode transition plan."""

    feature: SeatFeature
    level: int


SEAT_DEFINITIONS = (
    SeatDefinition(
        position=SeatPosition.FRONT_LEFT,
        translation_key="seat_front_left",
        heater="climate_state_seat_heater_left",
        ventilation="climate_state_seat_fan_front_left",
        auto="climate_state_auto_seat_climate_left",
        api_position=0,
        auto_api_position=1,
    ),
    SeatDefinition(
        position=SeatPosition.FRONT_RIGHT,
        translation_key="seat_front_right",
        heater="climate_state_seat_heater_right",
        ventilation="climate_state_seat_fan_front_right",
        auto="climate_state_auto_seat_climate_right",
        api_position=1,
        auto_api_position=2,
    ),
    SeatDefinition(
        position=SeatPosition.REAR_LEFT,
        translation_key="seat_rear_left",
        heater="climate_state_seat_heater_rear_left",
        api_position=2,
    ),
    SeatDefinition(
        position=SeatPosition.REAR_RIGHT,
        translation_key="seat_rear_right",
        heater="climate_state_seat_heater_rear_right",
        api_position=5,
    ),
)


def _level(value: object) -> int | None:
    """Return a valid Tesla seat level integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= 3 else None


def option_from_level(level: object) -> str | None:
    """Translate a Tesla numeric rear-seat heater level to an option."""
    value = _level(level)
    return _LEVEL_NAMES[value] if value is not None else None


def front_option_from_levels(
    heater_level: object,
    ventilation_level: object,
    auto_enabled: object,
) -> str | None:
    """Combine front automatic, heating, and ventilation telemetry."""
    if auto_enabled is True:
        return "auto"
    heater = _level(heater_level)
    ventilation = _level(ventilation_level)
    if heater == 0 and ventilation == 0:
        return "off"
    if heater is not None and heater > 0 and ventilation in (None, 0):
        return f"heat_{_LEVEL_NAMES[heater]}"
    if ventilation is not None and ventilation > 0 and heater in (None, 0):
        return f"ventilation_{_LEVEL_NAMES[ventilation]}"
    return None


def seat_command_plan(
    definition: SeatDefinition,
    option: str,
) -> tuple[SeatCommand, ...]:
    """Build a safe command plan; front heat and ventilation never overlap."""
    if option not in definition.options:
        raise ValueError(f"Unsupported option {option} for {definition.position}")

    if definition.ventilation is None:
        return (
            SeatCommand(
                SeatFeature.HEATER,
                REAR_SEAT_OPTIONS.index(option),
            ),
        )

    if option == "auto":
        return (
            SeatCommand(SeatFeature.HEATER, 0),
            SeatCommand(SeatFeature.VENTILATION, 0),
            SeatCommand(SeatFeature.AUTO, 1),
        )

    if option == "off":
        return (
            SeatCommand(SeatFeature.AUTO, 0),
            SeatCommand(SeatFeature.HEATER, 0),
            SeatCommand(SeatFeature.VENTILATION, 0),
        )

    feature_name, level_name = option.rsplit("_", maxsplit=1)
    level = _LEVEL_NAMES.index(level_name)
    if feature_name == "heat":
        return (
            SeatCommand(SeatFeature.AUTO, 0),
            SeatCommand(SeatFeature.VENTILATION, 0),
            SeatCommand(SeatFeature.HEATER, level),
        )
    return (
        SeatCommand(SeatFeature.AUTO, 0),
        SeatCommand(SeatFeature.HEATER, 0),
        SeatCommand(SeatFeature.VENTILATION, level),
    )
