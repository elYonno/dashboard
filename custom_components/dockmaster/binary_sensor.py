"""Binary sensors: NAS connectivity and running state of each compose service."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DockmasterConfigEntry
from .coordinator import DockmasterCoordinator
from .entity import DockmasterEntity, app_device, dashboard_device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockmasterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([DockmasterConnectedSensor(coordinator, entry)])

    # One entity per service. Apps can be added on the server at any time,
    # so new ones are discovered on every coordinator update.
    known: set[str] = set()

    @callback
    def _discover_services() -> None:
        new: list[BinarySensorEntity] = []
        for app in coordinator.data["apps"]:
            for svc in app["services"]:
                uid = f"{entry.entry_id}_{app['host']}_{app['name']}_{svc['name']}"
                if uid in known:
                    continue
                known.add(uid)
                new.append(
                    DockmasterServiceSensor(
                        coordinator, entry, app["host"], app["name"], svc["name"]
                    )
                )
        if new:
            async_add_entities(new)

    _discover_services()
    entry.async_on_unload(coordinator.async_add_listener(_discover_services))


class DockmasterConnectedSensor(DockmasterEntity, BinarySensorEntity):
    """Whether the Dockmaster server can reach the NAS over SSH."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "NAS connection"

    def __init__(self, coordinator: DockmasterCoordinator, entry: DockmasterConfigEntry) -> None:
        super().__init__(coordinator, f"{entry.entry_id}_connected", dashboard_device(entry))

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["health"].get("connected"))


class DockmasterServiceSensor(DockmasterEntity, BinarySensorEntity):
    """True while a compose service is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: DockmasterCoordinator,
        entry: DockmasterConfigEntry,
        host: str,
        app: str,
        service: str,
    ) -> None:
        super().__init__(
            coordinator,
            f"{entry.entry_id}_{host}_{app}_{service}",
            app_device(entry, host, app),
        )
        self._host = host
        self._app = app
        self._service = service
        self._attr_name = service

    def _service_state(self) -> str | None:
        for app in self.coordinator.data["apps"]:
            if app["host"] == self._host and app["name"] == self._app:
                for svc in app["services"]:
                    if svc["name"] == self._service:
                        return svc["state"]
        return None

    @property
    def available(self) -> bool:
        return super().available and self._service_state() is not None

    @property
    def is_on(self) -> bool:
        return self._service_state() == "running"
