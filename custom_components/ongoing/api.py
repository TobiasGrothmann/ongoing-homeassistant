"""Client for the Ongoing group endpoint.

The endpoint is a Cloud Function in the app's Firebase project. It takes the
group key in the `X-Group-Key` header (Cloud Run swallows bearer tokens) and
answers with the group's live notes::

    {"group": {"key": "...", "name": "..."},
     "notes": [{"id": "...", "content": "...", "due": "YYYY-MM-DD",
                "lastDone": "ISO 8601 or null", "isRecurring": true,
                "durationType": "days|weeks|months", "durationNumber": 1,
                "nextVariant": ""}],
     "serverTime": "ISO 8601"}

Deleted notes are not part of the answer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
import socket
from typing import Any, Self
import uuid

from aiohttp import ClientError, ClientSession

from .const import ENDPOINT_URL, LOGGER

USER_AGENT = "HomeAssistant-ongoing"


class OngoingError(Exception):
    """Generic Ongoing error."""


class OngoingConnectionError(OngoingError):
    """The endpoint could not be reached."""


class OngoingAuthenticationError(OngoingError):
    """The endpoint rejected the group key."""


def normalize_group_key(value: str) -> str:
    """Return the group key in canonical form.

    Raises ValueError when the value is not a UUID.
    """
    try:
        return str(uuid.UUID(value.strip()))
    except (AttributeError, TypeError, ValueError) as err:
        raise ValueError("A group key is a UUID") from err


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True, kw_only=True)
class OngoingNote:
    """A note of a shared list."""

    id: str
    content: str
    due: date
    last_done: datetime | None
    is_recurring: bool
    duration_type: str | None
    duration_number: int | None
    next_variant: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Build a note from an endpoint payload.

        Raises ValueError when the note has no id or no due date.
        """
        note_id = _as_str(data.get("id"))
        due = _parse_date(data.get("due"))
        if note_id is None or due is None:
            raise ValueError("A note needs an id and a due date")
        return cls(
            id=note_id,
            content=str(data.get("content") or "").strip(),
            due=due,
            last_done=_parse_datetime(data.get("lastDone")),
            is_recurring=bool(data.get("isRecurring", True)),
            duration_type=_as_str(data.get("durationType")),
            duration_number=_as_int(data.get("durationNumber")),
            next_variant=_as_str(data.get("nextVariant")),
        )

    @property
    def title(self) -> str:
        """The content, followed by the variant that is up next."""
        if self.next_variant:
            return f"{self.content} · {self.next_variant}"
        return self.content


@dataclass(frozen=True, kw_only=True)
class OngoingGroup:
    """A shared list with its notes, sorted by due date, then content."""

    key: str
    name: str
    notes: list[OngoingNote]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Build a group from an endpoint payload, skipping unreadable notes."""
        group = data.get("group")
        raw_notes = data.get("notes")
        if not isinstance(group, dict) or not isinstance(raw_notes, list):
            raise OngoingError("Unexpected response from the Ongoing endpoint")
        key = _as_str(group.get("key"))
        if key is None:
            raise OngoingError("The Ongoing endpoint answered without a group key")
        notes: list[OngoingNote] = []
        for item in raw_notes:
            if not isinstance(item, dict):
                continue
            try:
                notes.append(OngoingNote.from_dict(item))
            except ValueError as err:
                LOGGER.warning("Skipping unreadable note %s: %s", item.get("id"), err)
        notes.sort(key=lambda note: (note.due, note.content.casefold()))
        return cls(
            key=key,
            name=_as_str(group.get("name")) or f"Ongoing {key[:8]}",
            notes=notes,
        )

    def due_on_or_before(self, day: date) -> list[OngoingNote]:
        """Notes due on `day` or earlier, what the app's widget shows."""
        return [note for note in self.notes if note.due <= day]

    def due_before(self, day: date) -> list[OngoingNote]:
        """Notes whose due date has passed."""
        return [note for note in self.notes if note.due < day]


class OngoingClient:
    """Reads one shared list from the endpoint."""

    def __init__(
        self,
        group_key: str,
        session: ClientSession,
        *,
        endpoint: str = ENDPOINT_URL,
        request_timeout: float = 15,
    ) -> None:
        """Initialize the client. `group_key` must already be normalized."""
        self.group_key = group_key
        self._session = session
        self._endpoint = endpoint
        self._request_timeout = request_timeout

    async def async_fetch_group(self) -> OngoingGroup:
        """Return the group with its live notes."""
        headers = {
            "Accept": "application/json",
            "X-Group-Key": self.group_key,
            "User-Agent": USER_AGENT,
        }
        try:
            async with asyncio.timeout(self._request_timeout):
                response = await self._session.get(self._endpoint, headers=headers)
                if response.status in (401, 403, 404):
                    raise OngoingAuthenticationError(
                        "The Ongoing endpoint rejected the group key"
                    )
                if response.status >= 400:
                    body = (await response.text())[:300]
                    raise OngoingError(
                        f"The Ongoing endpoint answered HTTP {response.status}: {body}"
                    )
                try:
                    data = await response.json(content_type=None)
                except (ValueError, ClientError) as err:
                    raise OngoingError(
                        "The Ongoing endpoint returned a response that is not JSON"
                    ) from err
        except (TimeoutError, ClientError, socket.gaierror) as err:
            raise OngoingConnectionError(
                f"Error communicating with the Ongoing endpoint: {err}"
            ) from err
        if not isinstance(data, dict):
            raise OngoingError("Unexpected response from the Ongoing endpoint")
        return OngoingGroup.from_dict(data)
