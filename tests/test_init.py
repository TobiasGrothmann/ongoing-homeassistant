"""Tests for setup, the device and the poll cycle."""

from dataclasses import replace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.ongoing.api import (
    OngoingAuthenticationError,
    OngoingConnectionError,
)
from custom_components.ongoing.const import DEFAULT_SCAN_INTERVAL, DOMAIN

from . import setup_integration
from .conftest import GROUP_KEY


async def test_load_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """The entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (OngoingAuthenticationError("nope"), ConfigEntryState.SETUP_ERROR),
        (OngoingConnectionError("down"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """A rejected key stops setup; a connection failure retries."""
    mock_client.async_fetch_group.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_rejected_key_starts_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """A rejected key starts a reauth flow."""
    mock_client.async_fetch_group.side_effect = OngoingAuthenticationError("nope")
    await setup_integration(hass, mock_config_entry)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_device_follows_group_rename(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The list is one service device; renaming it in the app renames it here."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, GROUP_KEY), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Haushalt"
    assert device.entry_type is dr.DeviceEntryType.SERVICE

    group = mock_client.async_fetch_group.return_value
    mock_client.async_fetch_group.return_value = replace(group, name="Zuhause")
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, GROUP_KEY), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Zuhause"
    assert mock_config_entry.title == "Zuhause"


async def test_update_failure_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed poll makes entities unavailable; the next success restores them."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.haushalt_notes").state == "3"

    mock_client.async_fetch_group.side_effect = OngoingConnectionError("down")
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.haushalt_notes").state == "unavailable"

    mock_client.async_fetch_group.side_effect = None
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.haushalt_notes").state == "3"
