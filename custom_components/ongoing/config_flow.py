"""Config flow for the Ongoing integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import probatio

from .api import (
    OngoingAuthenticationError,
    OngoingClient,
    OngoingError,
    normalize_group_key,
)
from .const import CONF_GROUP_KEY, DOMAIN, LOGGER

EXAMPLE_KEY = "6f1c2a3e-8b4d-4c5e-9f60-1a2b3c4d5e6f"

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_GROUP_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class OngoingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for one shared list."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user, reauth and reconfigure steps (same form)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                group_key = normalize_group_key(user_input[CONF_GROUP_KEY])
            except ValueError:
                errors[CONF_GROUP_KEY] = "invalid_key"
            else:
                errors, title = await self._async_validate(group_key)
                if not errors:
                    return await self._async_finish(group_key, title)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={"example_key": EXAMPLE_KEY},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication after the endpoint rejected the key."""
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration (another group key)."""
        return await self.async_step_user()

    async def _async_validate(self, group_key: str) -> tuple[dict[str, str], str]:
        """Fetch the group; return form errors, or the group name as title."""
        client = OngoingClient(group_key, async_get_clientsession(self.hass))
        try:
            group = await client.async_fetch_group()
        except OngoingAuthenticationError:
            return {"base": "invalid_auth"}, ""
        except OngoingError:
            return {"base": "cannot_connect"}, ""
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error while validating the group key")
            return {"base": "unknown"}, ""
        return {}, group.name

    async def _async_finish(self, group_key: str, title: str) -> ConfigFlowResult:
        """Create or update the config entry."""
        existing = await self.async_set_unique_id(group_key)
        data = {CONF_GROUP_KEY: group_key}

        if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            entry = (
                self._get_reauth_entry()
                if self.source == SOURCE_REAUTH
                else self._get_reconfigure_entry()
            )
            if existing is not None and existing.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")
            return self.async_update_reload_and_abort(
                entry, data_updates=data, title=title, unique_id=group_key
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)
