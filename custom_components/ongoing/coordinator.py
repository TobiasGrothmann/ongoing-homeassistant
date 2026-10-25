"""Data update coordinator for the Ongoing integration."""

from __future__ import annotations

from datetime import date, datetime
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import OngoingAuthenticationError, OngoingClient, OngoingError, OngoingGroup
from .const import CONF_GROUP_KEY, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type OngoingConfigEntry = ConfigEntry[OngoingCoordinator]


class OngoingCoordinator(DataUpdateCoordinator[OngoingGroup]):
    """Polls one shared list."""

    config_entry: OngoingConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: OngoingConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = OngoingClient(
            config_entry.data[CONF_GROUP_KEY], async_get_clientsession(hass)
        )
        # Due counts depend on the calendar day, so entities must refresh at
        # midnight even when no note changed.
        config_entry.async_on_unload(
            async_track_time_change(hass, self._async_midnight, hour=0, minute=0)
        )

    @property
    def group_key(self) -> str:
        """The group key this entry reads."""
        return self.client.group_key

    def today(self) -> date:
        """The calendar day in Home Assistant's time zone."""
        return dt_util.now().date()

    @callback
    def _async_midnight(self, _now: datetime) -> None:
        self.async_update_listeners()

    @override
    async def _async_update_data(self) -> OngoingGroup:
        """Fetch the group from the endpoint."""
        try:
            group = await self.client.async_fetch_group()
        except OngoingAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from err
        except OngoingError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if self.data is not None and group.name != self.data.name:
            self._rename(group.name)
        return group

    def _rename(self, name: str) -> None:
        """Follow a group rename in the app."""
        self.hass.config_entries.async_update_entry(self.config_entry, title=name)
        registry = dr.async_get(self.hass)
        if device := registry.async_get_device_by_identifier(
            (DOMAIN, self.group_key), self.config_entry.entry_id
        ):
            registry.async_update_device(device.id, name=name)
