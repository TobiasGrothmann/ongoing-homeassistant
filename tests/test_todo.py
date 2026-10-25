"""Tests for the Ongoing to-do list."""

from unittest.mock import AsyncMock

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import setup_integration


async def test_todo_list(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Every note is an open item with its due date; the list is read-only."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("todo.haushalt")
    assert state is not None
    assert state.state == "3"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    response = await hass.services.async_call(
        TODO_DOMAIN,
        "get_items",
        {ATTR_ENTITY_ID: "todo.haushalt"},
        blocking=True,
        return_response=True,
    )
    items = response["todo.haushalt"]["items"]
    assert [item["summary"] for item in items] == [
        "Water the plants",
        "Take out the bins · Paper",
        "File taxes",
    ]
    assert items[0] == {
        "uid": "note-plants",
        "summary": "Water the plants",
        "status": "needs_action",
        "due": "2026-10-23",
    }
