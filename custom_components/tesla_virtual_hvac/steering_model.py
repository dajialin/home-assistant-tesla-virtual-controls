"""Pure steering-wheel heater mode mappings."""

from dataclasses import dataclass
from enum import StrEnum

STEERING_OPTIONS = ["off", "low", "high", "auto"]
_MANUAL_LEVELS = {"off": 0, "low": 1, "high": 2}


class SteeringFeature(StrEnum):
    """A remotely controllable steering-wheel comfort feature."""

    AUTO = "auto"
    HEATER = "heater"


@dataclass(frozen=True, slots=True)
class SteeringCommand:
    """One command in a steering-wheel mode transition."""

    feature: SteeringFeature
    value: int | bool


def steering_option_from_values(
    heater_level: object,
    auto_enabled: object,
) -> str | None:
    """Combine automatic and manual steering-wheel telemetry."""
    if auto_enabled is True:
        return "auto"
    if isinstance(heater_level, bool) or not isinstance(heater_level, int):
        return None
    return {0: "off", 1: "low", 2: "high"}.get(heater_level)


def steering_command_plan(option: str) -> tuple[SteeringCommand, ...]:
    """Build a transition that never leaves auto and manual heat enabled."""
    if option not in STEERING_OPTIONS:
        raise ValueError(f"Unsupported steering-wheel option: {option}")
    if option == "auto":
        return (
            SteeringCommand(SteeringFeature.HEATER, 0),
            SteeringCommand(SteeringFeature.AUTO, True),
        )
    return (
        SteeringCommand(SteeringFeature.AUTO, False),
        SteeringCommand(SteeringFeature.HEATER, _MANUAL_LEVELS[option]),
    )
