"""TeslaMate-backed state helpers for command-only Tesla Fleet entities."""

from __future__ import annotations

from math import isfinite
from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Event, State, callback
from homeassistant.helpers.event import async_track_state_change_event


def binary_state(state: State | Any | None) -> bool | None:
    """Convert one Home Assistant binary state without guessing unknown values."""
    if state is None:
        return None
    if state.state == STATE_ON:
        return True
    if state.state == STATE_OFF:
        return False
    return None


def numeric_state(state: State | Any | None) -> float | None:
    """Return one finite numeric TeslaMate value, or None when unavailable."""
    if state is None:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


class TeslaMateStateMixin:
    """Subscribe to a TeslaMate entity while Fleet remains command-only."""

    _teslamate_entity_id: str

    @property
    def telemetry_entity_id(self) -> str:
        """Return the configured TeslaMate source entity."""
        return self._teslamate_entity_id

    @property
    def available(self) -> bool:
        """Remain command-capable even while telemetry is temporarily unknown."""
        return True

    async def async_added_to_hass(self) -> None:
        """Subscribe to the configured TeslaMate source entity."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._teslamate_entity_id],
                self._async_teslamate_state_changed,
            )
        )
        self._update_from_teslamate_state(
            self.hass.states.get(self._teslamate_entity_id)
        )

    @callback
    def _async_teslamate_state_changed(self, event: Event) -> None:
        """Update one entity from TeslaMate without reading Fleet telemetry."""
        self._update_from_teslamate_state(event.data.get("new_state"))
        self.async_write_ha_state()

    def _update_from_teslamate_state(self, state: State | Any | None) -> None:
        """Apply one TeslaMate state in a concrete entity."""
        raise NotImplementedError
