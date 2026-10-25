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

    overdue = hass.states.get("sensor.haushalt_overdue")
    assert overdue.state == "1"
    assert [note["content"] for note in overdue.attributes["notes"]] == [
        "Water the plants"
    ]

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
    """A note due tomorrow becomes due at midnight without new data."""
    await setup_integration(hass, mock_config_entry)

    freezer.tick(timedelta(hours=11, minutes=59, seconds=59))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.haushalt_overdue").state == "1"
    polls = mock_client.async_fetch_group.await_count

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.haushalt_overdue").state == "2"
    assert mock_client.async_fetch_group.await_count == polls
