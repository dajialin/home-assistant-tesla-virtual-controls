"""Tesla Fleet command transport without coordinator telemetry coupling."""

import asyncio
from typing import Any

from homeassistant.components.tesla_fleet.const import DOMAIN as TESLA_FLEET_DOMAIN
from homeassistant.components.tesla_fleet.helpers import wake_up_vehicle
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import Entity
from tesla_fleet_api.const import Scope


class TeslaCommandEntity(Entity):
    """Base entity that can command a vehicle but never refresh Fleet state."""

    _attr_should_poll = False

    def __init__(self, vehicle: Any, scoped: bool) -> None:
        """Store command transport, scope state, and per-entity serialization."""
        super().__init__()
        self._command_lock = asyncio.Lock()
        self.vehicle = vehicle
        self.api = vehicle.api
        self.scoped = scoped

    async def wake_up_if_asleep(self) -> None:
        """Wake the vehicle only as part of an explicit command."""
        await wake_up_vehicle(self.vehicle)

    def raise_for_read_only(self, scope: Scope) -> None:
        """Raise the same translated scope error as Tesla Fleet."""
        if not self.scoped:
            raise ServiceValidationError(
                translation_domain=TESLA_FLEET_DOMAIN,
                translation_key=f"missing_scope_{scope.name.lower()}",
            )
