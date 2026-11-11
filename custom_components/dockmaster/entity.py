"""Shared base entity and device helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HOST_LABELS
from .coordinator import DockmasterCoordinator
from . import DockmasterConfigEntry


def dashboard_device(entry: DockmasterConfigEntry) -> DeviceInfo:
    """The Dockmaster server itself (connectivity and bulk actions)."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Dockmaster",
        manufacturer="Dockmaster",
    )


def host_device(entry: DockmasterConfigEntry, host_id: str) -> DeviceInfo:
    """A machine Dockmaster monitors: 'nas' (over SSH) or 'pi' (local)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{host_id}")},
        name=f"Dockmaster {HOST_LABELS.get(host_id, host_id)}",
        manufacturer="Dockmaster",
    )


def app_device(entry: DockmasterConfigEntry, host_id: str, app: str) -> DeviceInfo:
    """One compose app on one host; its services are entities of this device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{host_id}_{app}")},
        name=app,
        manufacturer="Docker Compose",
        model=f"App on {HOST_LABELS.get(host_id, host_id)}",
    )


class DockmasterEntity(CoordinatorEntity[DockmasterCoordinator]):
    """Base class: entity name is relative to its device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DockmasterCoordinator,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
