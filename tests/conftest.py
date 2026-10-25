"""Common fixtures for the Ongoing tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ongoing.api import OngoingGroup
from custom_components.ongoing.const import CONF_GROUP_KEY, DOMAIN

from . import load_fixture

GROUP_KEY = "11111111-2222-4333-8444-555555555555"

# Noon in US/Pacific, the time zone of a test Home Assistant. The fixture has
# a note due two days earlier, one due today and one in November.
TODAY = "2026-10-25 12:00:00-07:00"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture(autouse=True)
def today(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Pin the calendar day the fixture notes are measured against."""
    freezer.move_to(TODAY)
    return freezer


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.ongoing.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Haushalt",
        unique_id=GROUP_KEY,
        data={CONF_GROUP_KEY: GROUP_KEY},
    )


def fixture_group() -> OngoingGroup:
    """Return the group from the fixture file."""
    return OngoingGroup.from_dict(json.loads(load_fixture("group.json")))


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the client in the coordinator and the config flow."""
    with (
        patch(
            "custom_components.ongoing.coordinator.OngoingClient",
            autospec=True,
        ) as mock_client,
        patch(
            "custom_components.ongoing.config_flow.OngoingClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.group_key = GROUP_KEY
        client.async_fetch_group.return_value = fixture_group()
        yield client
