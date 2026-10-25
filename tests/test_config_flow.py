"""Tests for the Ongoing config flow."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ongoing.api import (
    OngoingAuthenticationError,
    OngoingConnectionError,
)
from custom_components.ongoing.const import CONF_GROUP_KEY, DOMAIN

from .conftest import GROUP_KEY

USER_INPUT = {CONF_GROUP_KEY: f" {GROUP_KEY.upper()} "}
OTHER_KEY = "99999999-8888-4777-8666-555555555555"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """A valid key creates an entry named after the group."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Haushalt"
    assert result["data"] == {CONF_GROUP_KEY: GROUP_KEY}
    assert result["result"].unique_id == GROUP_KEY
    mock_client.async_fetch_group.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_invalid_key(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """A value that is not a UUID is reported on the field without a request."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_GROUP_KEY: "Haushalt"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_GROUP_KEY: "invalid_key"}
    mock_client.async_fetch_group.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (OngoingAuthenticationError("nope"), "invalid_auth"),
        (OngoingConnectionError("down"), "cannot_connect"),
        (RuntimeError("weird"), "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Endpoint problems show an error and the flow can recover."""
    mock_client.async_fetch_group.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.async_fetch_group.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The same list cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_reauth(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Reauth can move the entry to another key."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_GROUP_KEY: OTHER_KEY}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_GROUP_KEY] == OTHER_KEY
    assert mock_config_entry.unique_id == OTHER_KEY


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_reconfigure_to_existing_list_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfiguring onto a key owned by another entry is refused."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, unique_id=OTHER_KEY, data={CONF_GROUP_KEY: OTHER_KEY}
    )
    other.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_GROUP_KEY: OTHER_KEY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_GROUP_KEY] == GROUP_KEY
