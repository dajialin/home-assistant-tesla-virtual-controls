"""Pure latest-value selection helpers for Tesla Virtual Controls."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")


def as_float(value: object) -> float | None:
    """Return a finite numeric state value, or None when unavailable."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def mqtt_hvac_mode(state: str) -> str | None:
    """Map TeslaMate's climate switch state to Tesla Fleet HVAC modes."""
    if state == "on":
        return "heat_cool"
    if state == "off":
        return "off"
    return None


@dataclass(frozen=True, slots=True)
class TimedValue(Generic[T]):
    """A source value and the instant when that value last changed."""

    source: str
    value: T
    changed_at: datetime


class LatestValueTracker(Generic[T]):
    """Choose the most recently changed valid value across sources."""

    def __init__(self, validator: Callable[[T], bool]) -> None:
        self._validator = validator
        self._observed: dict[str, T] = {}
        self._samples: dict[str, TimedValue[T]] = {}

    def observe(self, source: str, value: T, changed_at: datetime) -> bool:
        """Record a source value and report whether a new valid sample was stored."""
        if not self._validator(value):
            return False
        if source in self._observed and self._observed[source] == value:
            return False
        self._observed[source] = value
        self._samples[source] = TimedValue(source, value, changed_at)
        return True

    def latest(self) -> TimedValue[T] | None:
        """Return the newest valid value, preferring Fleet on an exact tie."""
        candidates = [
            sample for sample in self._samples.values() if self._validator(sample.value)
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda sample: (sample.changed_at, sample.source == "fleet"),
        )


@dataclass(frozen=True, slots=True)
class TeslaHvacSnapshot:
    """The selected Tesla HVAC values and their winning sources."""

    hvac_mode: TimedValue[str] | None
    current_temperature: TimedValue[float] | None
    target_temperature: TimedValue[float] | None
    preset_mode: TimedValue[str] | None


class TeslaHvacModel:
    """Track TeslaMate values independently per HVAC field."""

    def __init__(self) -> None:
        def valid_temperature(value: object) -> bool:
            return as_float(value) is not None

        self._hvac = LatestValueTracker[str | None](
            lambda value: value in {"heat_cool", "off"}
        )
        self._current_temperature = LatestValueTracker[float | None](valid_temperature)
        self._target_temperature = LatestValueTracker[float | None](valid_temperature)
        self._preset = LatestValueTracker[str | None](
            lambda value: value in {"off", "keep", "dog", "camp"}
        )

    def observe_mqtt_hvac(self, state: str, changed_at: datetime) -> bool:
        """Observe TeslaMate's MQTT climate-on state."""
        return self._hvac.observe("mqtt", mqtt_hvac_mode(state), changed_at)

    def observe_mqtt_current_temperature(
        self, value: object, changed_at: datetime
    ) -> bool:
        """Observe TeslaMate's MQTT cabin temperature."""
        return self._current_temperature.observe("mqtt", as_float(value), changed_at)

    def observe_teslamate_target_temperature(
        self, value: object, changed_at: datetime
    ) -> bool:
        """Observe the TeslaMate-derived driver setpoint."""
        return self._target_temperature.observe(
            "teslamate", as_float(value), changed_at
        )

    def observe_mqtt_preset(self, value: str, changed_at: datetime) -> bool:
        """Observe TeslaMate's MQTT climate keeper mode."""
        return self._preset.observe("mqtt", value, changed_at)

    def snapshot(self) -> TeslaHvacSnapshot:
        """Return the newest valid value selected independently for each field."""
        return TeslaHvacSnapshot(
            hvac_mode=self._hvac.latest(),
            current_temperature=self._current_temperature.latest(),
            target_temperature=self._target_temperature.latest(),
            preset_mode=self._preset.latest(),
        )
