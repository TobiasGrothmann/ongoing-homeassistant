"""Tests for the endpoint client and its parsing."""

from datetime import date

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.ongoing.api import (
    OngoingAuthenticationError,
    OngoingClient,
    OngoingError,
    normalize_group_key,
)
from custom_components.ongoing.const import ENDPOINT_URL

from . import load_fixture
from .conftest import GROUP_KEY, fixture_group


def test_parsing_sorts_and_skips_unreadable_notes() -> None:
    """Notes come sorted by due date; a note without a due date is dropped."""
    group = fixture_group()
    assert group.key == GROUP_KEY
    assert group.name == "Haushalt"
    assert [note.id for note in group.notes] == ["note-plants", "note-bins", "note-tax"]
    bins = group.notes[1]
    assert bins.due == date(2026, 10, 25)
    assert bins.title == "Take out the bins · Paper"
    assert group.notes[0].title == "Water the plants"
    assert group.notes[0].last_done is not None
    assert group.notes[2].is_recurring is False


def test_due_selection() -> None:
    """Due means today or earlier."""
    group = fixture_group()
    today = date(2026, 10, 25)
    assert [n.id for n in group.due_on_or_before(today)] == ["note-plants", "note-bins"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" 11111111-2222-4333-8444-555555555555 ", GROUP_KEY),
        ("11111111222243338444555555555555", GROUP_KEY),
        ("11111111-2222-4333-8444-55555555555", None),
        ("not a key", None),
    ],
)
def test_normalize_group_key(value: str, expected: str | None) -> None:
    """Keys are accepted in any UUID spelling and refused otherwise."""
    if expected is None:
        with pytest.raises(ValueError):
            normalize_group_key(value)
    else:
        assert normalize_group_key(value) == expected


async def test_fetch_sends_key_header(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The group key travels in a header, never in the URL."""
    aioclient_mock.get(ENDPOINT_URL, text=load_fixture("group.json"))
    client = OngoingClient(GROUP_KEY, async_get_clientsession(hass))

    group = await client.async_fetch_group()

    assert len(group.notes) == 3
    assert len(aioclient_mock.mock_calls) == 1
    _method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert headers["X-Group-Key"] == GROUP_KEY
    assert url.query_string == ""


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, OngoingAuthenticationError),
        (404, OngoingAuthenticationError),
        (500, OngoingError),
    ],
)
async def test_fetch_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    error: type[Exception],
) -> None:
    """A rejected key is an authentication error; anything else a plain error."""
    aioclient_mock.get(ENDPOINT_URL, status=status, text="nope")
    client = OngoingClient(GROUP_KEY, async_get_clientsession(hass))

    with pytest.raises(error):
        await client.async_fetch_group()
