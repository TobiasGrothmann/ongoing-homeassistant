"""Per-note due flags for the Ongoing integration."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OngoingConfigEntry, OngoingCoordinator
from .entity import OngoingNoteEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OngoingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one due flag per note, following notes added later."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _async_add_new_notes() -> None:
        current = set(coordinator.notes_by_id)
        known.intersection_update(current)
        new = current - known
        if new:
            async_add_entities(OngoingNoteDue(coordinator, note_id) for note_id in new)
            known.update(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_notes))
    _async_add_new_notes()


class OngoingNoteDue(OngoingNoteEntity, BinarySensorEntity):
    """On when the note is due today or earlier; the note's facts as attributes."""

    _attr_name = None
    _attr_translation_key = "due"

    def __init__(self, coordinator: OngoingCoordinator, note_id: str) -> None:
        """Initialize the due flag."""
        super().__init__(coordinator, note_id)
        self._attr_unique_id = f"{note_id}_due"

    @property
    @override
    def is_on(self) -> bool:
        """Return True when the note is due."""
        return self.note.due <= self.coordinator.today()

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Everything a dashboard or template needs about the note."""
        note = self.note
        recurring = note.is_recurring
        return {
            "content": note.name,
            "recurring": recurring,
            "interval": note.interval,
            "interval_number": note.duration_number if recurring else None,
            "interval_unit": note.duration_type if recurring else None,
            "due": note.due.isoformat(),
            "days_until_due": note.days_until_due(self.coordinator.today()),
            "last_done": note.last_done.isoformat() if note.last_done else None,
            "next_variant": note.next_variant,
            "note_id": note.id,
            "list": self.coordinator.data.name,
        }
