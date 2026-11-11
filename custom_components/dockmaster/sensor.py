"""Host and Docker sensors: CPU, RAM, temperature, uptime, container totals."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DockmasterConfigEntry
from .entity import DockmasterEntity, dashboard_device, host_device
from .coordinator import DockmasterCoordinator

# Keys are the field names returned by /api/system, /api/host and /api/stats.
HOST_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="cpu",
        name="CPU",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ramPct",
        name="RAM",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key="uptime", name="Uptime"),
)

# Container totals come from /api/stats, which only reports the NAS.
DOCKER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="containers",
        name="Containers running",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cpu",
        name="Container CPU",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="memMB",
        name="Container memory",
        native_unit_of_measurement="MiB",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockmasterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for source in ("nas", "pi"):
        entities += [
            DockmasterStatSensor(coordinator, entry, source, description)
            for description in HOST_SENSORS
        ]
    entities += [
        DockmasterStatSensor(coordinator, entry, "docker", description)
        for description in DOCKER_SENSORS
    ]
    async_add_entities(entities)


class DockmasterStatSensor(DockmasterEntity, SensorEntity):
    """One numeric field from one of the stats payloads."""

    def __init__(
        self,
        coordinator: DockmasterCoordinator,
        entry: DockmasterConfigEntry,
        source: str,
        description: SensorEntityDescription,
    ) -> None:
        # Docker totals belong to the NAS device.
        device_host = "nas" if source == "docker" else source
        super().__init__(
            coordinator,
            f"{entry.entry_id}_{source}_{description.key}",
            host_device(entry, device_host),
        )
        self.entity_description = description
        self._source = source

    @property
    def native_value(self):
        payload = self.coordinator.data.get(self._source)
        if payload is None:
            return None
        return payload.get(self.entity_description.key)
