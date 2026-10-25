"""The shared list as a to-do list."""

from __future__ import annotations

from typing import override

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OngoingConfigEntry, OngoingCoordinator
from .entity import OngoingEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OngoingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the to-do list for a shared list."""
    async_add_entities([OngoingTodoList(entry.runtime_data)])


class OngoingTodoList(OngoingEntity, TodoListEntity):
    """Every note of the list, read-only; the state is the note count."""

    _attr_name = None
    _attr_translation_key = "notes"
    _attr_supported_features = TodoListEntityFeature(0)

    def __init__(self, coordinator: OngoingCoordinator) -> None:
        """Initialize the to-do list."""
        super().__init__(coordinator)
        self._attr_unique_id = self._unique_id("notes")

    @property
    @override
    def todo_items(self) -> list[TodoItem] | None:
        """Return the notes as to-do items, due date included."""
        return [
            TodoItem(
                uid=note.id,
                summary=note.title,
                status=TodoItemStatus.NEEDS_ACTION,
                due=note.due,
            )
            for note in self.group_data.notes
        ]
