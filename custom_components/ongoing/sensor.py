"""Sensors for the Ongoing integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import OngoingGroup, OngoingNote
from .coordinator import OngoingConfigEntry, OngoingCoordinator
from .entity import OngoingEntity, OngoingNoteEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OngoingSensorEntityDescription(SensorEntityDescription):
    """Describes an Ongoing sensor.

    A sensor with `notes_fn` counts the notes it selects and lists them as
    the `notes` attribute, for templates and dashboards.
    """

    value_fn: Callable[[OngoingGroup, date], StateType | date] | None = None
    notes_fn: Callable[[OngoingGroup, date], list[OngoingNote]] | None = None


SENSOR_DESCRIPTIONS: tuple[OngoingSensorEntityDescription, ...] = (
    OngoingSensorEntityDescription(
        key="due",
        translation_key="due",
        state_class=SensorStateClass.MEASUREMENT,
        notes_fn=lambda group, today: group.due_on_or_before(today),
    ),
    OngoingSensorEntityDescription(
        key="next_due",
        translation_key="next_due",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda group, today: group.notes[0].due if group.notes else None,
    ),
    OngoingSensorEntityDescription(
        key="notes",
        translation_key="notes",
        state_class=SensorStateClass.MEASUREMENT,
        notes_fn=lambda group, today: group.notes,
    ),
)


def _note_attributes(note: OngoingNote) -> dict[str, Any]:
    return {
        "content": note.content,
        "variant": note.next_variant,
        "due": note.due.isoformat(),
        "recurring": note.is_recurring,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OngoingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the list sensors and one due-date sensor per note."""
    coordinator = entry.runtime_data
    async_add_entities(
        OngoingSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )

    known: set[str] = set()

    @callback
    def _async_add_new_notes() -> None:
        current = set(coordinator.notes_by_id)
        known.intersection_update(current)
        new = current - known
        if new:
            async_add_entities(
                entity
                for note_id in new
                for entity in (
                    OngoingNoteDueDate(coordinator, note_id),
                    OngoingNoteDueIn(coordinator, note_id),
                )
            )
            known.update(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_notes))
    _async_add_new_notes()


class OngoingSensor(OngoingEntity, SensorEntity):
    """Defines an Ongoing sensor."""

    entity_description: OngoingSensorEntityDescription

    def __init__(
        self,
        coordinator: OngoingCoordinator,
        description: OngoingSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self._unique_id(description.key)

    @property
    @override
    def native_value(self) -> StateType | date:
        """Return the state of the sensor."""
        today = self.coordinator.today()
        if self.entity_description.notes_fn is not None:
            return len(self.entity_description.notes_fn(self.group_data, today))
        assert self.entity_description.value_fn is not None
        return self.entity_description.value_fn(self.group_data, today)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """List the counted notes."""
        if self.entity_description.notes_fn is None:
            return None
        notes = self.entity_description.notes_fn(
            self.group_data, self.coordinator.today()
        )
        return {"notes": [_note_attributes(note) for note in notes]}


class OngoingNoteDueDate(OngoingNoteEntity, SensorEntity):
    """The day a note is due."""

    _attr_translation_key = "due_date"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: OngoingCoordinator, note_id: str) -> None:
        """Initialize the due-date sensor."""
        super().__init__(coordinator, note_id)
        self._attr_unique_id = f"{note_id}_due_date"

    @property
    @override
    def native_value(self) -> date:
        """Return the due date."""
        return self.note.due


class OngoingNoteDueIn(OngoingNoteEntity, SensorEntity):
    """Calendar days until a note is due; negative once it is overdue."""

    _attr_translation_key = "due_in"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: OngoingCoordinator, note_id: str) -> None:
        """Initialize the due-in sensor."""
        super().__init__(coordinator, note_id)
        self._attr_unique_id = f"{note_id}_due_in"

    @property
    @override
    def native_value(self) -> int:
        """Return the days until due."""
        return self.note.days_until_due(self.coordinator.today())
