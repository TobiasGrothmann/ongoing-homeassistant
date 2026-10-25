"""Tests for the Ongoing sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from . import setup_integration
from .conftest import GROUP_KEY


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Counts measure calendar days; the counted notes are attributes."""
    await setup_integration(hass, mock_config_entry)

    due = hass.states.get("sensor.haushalt_due")
    assert due is not None
    assert due.state == "2"
    assert [note["content"] for note in due.attributes["notes"]] == [
        "Water the plants",
        "Take out the bins",
    ]
    assert due.attributes["notes"][1] == {
        "content": "Take out the bins",
        "variant": "Paper",
        "due": "2026-10-25",
        "recurring": True,
    }

    assert hass.states.get("sensor.haushalt_next_due").state == "2026-10-23"
    assert hass.states.get("sensor.haushalt_notes").state == "3"

    entry = entity_registry.async_get("sensor.haushalt_due")
    assert entry is not None
    assert entry.unique_id == f"{GROUP_KEY}_due"


async def test_counts_roll_over_at_midnight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The due count follows the calendar day without new data."""
    # The taxes note is due on 30 Nov; start on the evening before.
    freezer.move_to("2026-11-29 23:59:59-08:00")
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.haushalt_due").state == "2"
    polls = mock_client.async_fetch_group.await_count

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.haushalt_due").state == "3"
    assert mock_client.async_fetch_group.await_count == polls
