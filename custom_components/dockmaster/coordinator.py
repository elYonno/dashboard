"""Polls the Dockmaster server and shares the result with all entities."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DockmasterClient, DockmasterError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class DockmasterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches apps, host stats and NAS health in one update cycle."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: DockmasterClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        # Apps and health are required: without them there is nothing useful to show.
        try:
            apps, health = await asyncio.gather(
                self.client.get_apps(), self.client.get_health()
            )
        except DockmasterError as err:
            raise UpdateFailed(f"Cannot reach Dockmaster: {err}") from err

        # Host stats are optional, so one failing source (e.g. NAS SSH down)
        # does not make every entity unavailable.
        nas, pi, docker = await asyncio.gather(
            _optional(self.client.get_nas_stats()),
            _optional(self.client.get_pi_stats()),
            _optional(self.client.get_docker_stats()),
        )
        return {
            "apps": apps,
            "health": health,
            "nas": nas,
            "pi": pi,
            "docker": docker,
        }


async def _optional(request: Awaitable[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        return await request
    except DockmasterError as err:
        _LOGGER.debug("Optional Dockmaster data unavailable: %s", err)
        return None
