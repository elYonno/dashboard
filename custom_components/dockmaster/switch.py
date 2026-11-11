"""One switch per compose app: on = at least one service running; toggling runs compose up/stop."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DockmasterConfigEntry
from .api import DockmasterError
from .coordinator import DockmasterCoordinator
from .entity import DockmasterEntity, app_device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockmasterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _discover_apps() -> None:
        new: list[SwitchEntity] = []
        for app in coordinator.data["apps"]:
            uid = f"{entry.entry_id}_{app['host']}_{app['name']}_app"
            if uid in known:
                continue
            known.add(uid)
            new.append(DockmasterAppSwitch(coordinator, entry, app["host"], app["name"]))
        if new:
            async_add_entities(new)

    _discover_apps()
    entry.async_on_unload(coordinator.async_add_listener(_discover_apps))


class DockmasterAppSwitch(DockmasterEntity, SwitchEntity):
    """Start (compose up -d) or stop (compose stop) a whole app."""

    # Primary entity of its device, so it takes the app's name.
    _attr_name = None

    def __init__(
        self,
        coordinator: DockmasterCoordinator,
        entry: DockmasterConfigEntry,
        host: str,
        app: str,
    ) -> None:
        super().__init__(
            coordinator,
            f"{entry.entry_id}_{host}_{app}_app",
            app_device(entry, host, app),
        )
        self._host = host
        self._app = app

    def _app_data(self) -> dict[str, Any] | None:
        for app in self.coordinator.data["apps"]:
            if app["host"] == self._host and app["name"] == self._app:
                return app
        return None

    @property
    def available(self) -> bool:
        return super().available and self._app_data() is not None

    @property
    def is_on(self) -> bool:
        app = self._app_data()
        return bool(app) and any(s["state"] == "running" for s in app["services"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._run("start")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run("stop")

    async def _run(self, action: str) -> None:
        try:
            await self.coordinator.client.app_action(self._host, self._app, action)
        except DockmasterError as err:
            raise HomeAssistantError(f"{self._app} {action} failed: {err}") from err
        await self.coordinator.async_request_refresh()
