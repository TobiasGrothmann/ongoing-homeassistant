"""Tests for the per-note devices and their entities."""

from dataclasses import replace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.ongoing.const import DEFAULT_SCAN_INTERVAL, DOMAIN

from . import setup_integration
from .conftest import GROUP_KEY


async def test_note_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Each note is a device under the list with a due flag and a due date."""
    await setup_integration(hass, mock_config_entry)

    plants = hass.states.get("binary_sensor.water_the_plants")
    assert plants is not None
    assert plants.state == STATE_ON
    assert plants.attributes["content"] == "Water the plants"
    assert plants.attributes["recurring"] is True
    assert plants.attributes["interval"] == "every week"
    assert plants.attributes["interval_number"] == 1
    assert plants.attributes["interval_unit"] == "weeks"
    assert plants.attributes["due"] == "2026-10-23"
    assert plants.attributes["days_until_due"] == -2
    assert plants.attributes["last_done"] == "2026-10-16T08:00:00"
    assert plants.attributes["next_variant"] is None
    assert plants.attributes["note_id"] == "note-plants"
    assert plants.attributes["list"] == "Haushalt"

    bins = hass.states.get("binary_sensor.take_out_the_bins")
    assert bins.state == STATE_ON
    assert bins.attributes["interval"] == "every 14 days"
    assert bins.attributes["next_variant"] == "Paper"
    assert bins.attributes["days_until_due"] == 0

    taxes = hass.states.get("binary_sensor.file_taxes")
    assert taxes.state == STATE_OFF
    assert taxes.attributes["recurring"] is False
    assert taxes.attributes["interval"] == "once"
    assert taxes.attributes["interval_number"] is None
    assert taxes.attributes["days_until_due"] == 36

    assert hass.states.get("sensor.water_the_plants_due_date").state == "2026-10-23"
    assert hass.states.get("sensor.water_the_plants_due_in").state == "-2"
    assert hass.states.get("sensor.file_taxes_due_in").state == "36"

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "note-plants"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Water the plants"
    assert device.model == "every week"
    parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, GROUP_KEY), mock_config_entry.entry_id
    )
    assert parent is not None
    assert device.via_device_id == parent.id


async def test_note_removed_and_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A deleted note loses its device; a new note gets one without a restart."""
    await setup_integration(hass, mock_config_entry)
    group = mock_client.async_fetch_group.return_value

    mock_client.async_fetch_group.return_value = replace(group, notes=group.notes[1:])
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.water_the_plants") is None
    assert hass.states.get("sensor.water_the_plants_due_date") is None
    assert hass.states.get("sensor.water_the_plants_due_in") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "note-plants"), mock_config_entry.entry_id
        )
        is None
    )
    assert hass.states.get("binary_sensor.take_out_the_bins").state == STATE_ON

    mock_client.async_fetch_group.return_value = group
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.water_the_plants").state == STATE_ON


async def test_note_rename_follows(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An edit in the app renames the device; the entity id stays."""
    await setup_integration(hass, mock_config_entry)
    group = mock_client.async_fetch_group.return_value
    plants = group.notes[0]
    edited = replace(plants, content="Water the balcony", duration_number=2)
    mock_client.async_fetch_group.return_value = replace(
        group, notes=[edited, *group.notes[1:]]
    )

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "note-plants"), mock_config_entry.entry_id
    )
    assert device.name == "Water the balcony"
    assert device.model == "every 2 weeks"
    state = hass.states.get("binary_sensor.water_the_plants")
    assert state is not None
    assert state.attributes["content"] == "Water the balcony"
    assert state.attributes["interval"] == "every 2 weeks"
