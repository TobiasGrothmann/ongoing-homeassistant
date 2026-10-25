"""Base entity for the Ongoing integration."""

from __future__ import annotations

from typing import override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OngoingGroup, OngoingNote
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


class OngoingNoteEntity(CoordinatorEntity[OngoingCoordinator]):
    """An entity of one note; the note is a device under the list."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OngoingCoordinator, note_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._note_id = note_id
        # The coordinator creates the device, with the list as its parent.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, note_id)})

    @property
    def note(self) -> OngoingNote:
        """The note from coordinator data."""
        return self.coordinator.notes_by_id[self._note_id]

    @property
    @override
    def available(self) -> bool:
        """Unavailable once the note is gone from the list."""
        return super().available and self._note_id in self.coordinator.notes_by_id
