"""Base entity for the Ongoing integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OngoingGroup
from .const import DOMAIN, MANUFACTURER
from .coordinator import OngoingCoordinator


class OngoingEntity(CoordinatorEntity[OngoingCoordinator]):
    """An entity of one shared list; the list is the device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OngoingCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.group_key)},
            name=coordinator.data.name,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def group_data(self) -> OngoingGroup:
        """The list from coordinator data."""
        return self.coordinator.data

    def _unique_id(self, key: str) -> str:
        """Return a unique id for an entity key of this list."""
        return f"{self.coordinator.group_key}_{key}"
