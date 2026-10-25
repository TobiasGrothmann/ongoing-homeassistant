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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import OngoingGroup, OngoingNote
from .coordinator import OngoingConfigEntry, OngoingCoordinator
from .entity import OngoingEntity

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
        key="overdue",
        translation_key="overdue",
        state_class=SensorStateClass.MEASUREMENT,
        notes_fn=lambda group, today: group.due_before(today),
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
    """Set up the sensors for a shared list."""
    coordinator = entry.runtime_data
    async_add_entities(
        OngoingSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


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
