"""Diagnostics support for the Ongoing integration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_GROUP_KEY
from .coordinator import OngoingConfigEntry

TO_REDACT = {CONF_GROUP_KEY, "key"}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OngoingConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    group = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "group": async_redact_data({"key": group.key, "name": group.name}, TO_REDACT),
        "notes": [
            {key: _jsonable(value) for key, value in asdict(note).items()}
            for note in group.notes
        ],
    }
