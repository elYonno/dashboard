"""Buttons to start or stop every app on every host."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DockmasterConfigEntry
from .api import DockmasterError
from .coordinator import DockmasterCoordinator
from .entity import DockmasterEntity, dashboard_device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockmasterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            DockmasterAllAppsButton(coordinator, entry, "start", "Start all apps"),
            DockmasterAllAppsButton(coordinator, entry, "stop", "Stop all apps"),
        ]
    )


class DockmasterAllAppsButton(DockmasterEntity, ButtonEntity):
    """Runs `docker compose up -d` or `stop` on all apps on all hosts."""

    def __init__(
        self,
        coordinator: DockmasterCoordinator,
        entry: DockmasterConfigEntry,
        action: str,
        name: str,
    ) -> None:
        super().__init__(
            coordinator, f"{entry.entry_id}_all_{action}", dashboard_device(entry)
        )
        self._action = action
        self._attr_name = name

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.all_apps_action(self._action)
        except DockmasterError as err:
            raise HomeAssistantError(f"{self._action} all failed: {err}") from err
        await self.coordinator.async_request_refresh()
