# Ongoing for Home Assistant

Shows a shared list of the [Ongoing](https://github.com/TobiasGrothmann/ongoing)
app in Home Assistant: what is due, what is overdue, and the whole list as a
to-do entity. Read-only for now.

> Written with Claude Code, reviewed and tested by a human on one list.
> Read the code before trusting it.

## How it works

The app keeps shared lists in Firestore. A Cloud Function in the app's
Firebase project (`groupNotes`) answers with the live notes of one list when
asked with that list's group key. This integration polls that function every
two minutes. Nothing but the group key ever leaves Home Assistant, and the key
travels in a request header, never in a URL.

The group key is the list's only credential, in the app as well: whoever has it
can read and edit the list.

## Install

**Requirements:** Home Assistant 2026.10+ and the group key of a shared list
(Ongoing app → Sharing → copy the key).

**HACS:** Integrations → ⋮ → *Custom repositories* → paste
`https://github.com/TobiasGrothmann/ongoing-homeassistant`, category
*Integration* → install → restart.

**Manual:** copy `custom_components/ongoing` into your `custom_components`
folder → restart. `scripts/deploy.sh` does that over SSH for a Home Assistant
OS box.

## Set up

Settings → Devices & services → *Add integration* → **Ongoing** → paste the
group key. The entry is named after the list and follows a rename in the app.
*Reconfigure* on the entry switches it to another key.

## What you get

One service device per list with:

| Entity | Meaning |
|---|---|
| `todo.<list>` | every note as an open item with its due date; the state is the note count |
| `sensor.<list>_due` | notes due today or earlier, what the app's widget shows; the notes are in the `notes` attribute |
| `sensor.<list>_overdue` | notes whose due date has passed, with the same attribute |
| `sensor.<list>_next_due` | the earliest due date |
| `sensor.<list>_notes` | all notes, with the same attribute |

And one device per note, under the list, named after the note's text, with
the interval as its model ("once", "every week", "every 2 weeks"). A note
device can be assigned to an area like any other device.

| Entity | Meaning |
|---|---|
| `binary_sensor.<note>` | on when the note is due today or earlier |
| `sensor.<note>_due_date` | the day it is due |

The binary sensor's attributes carry the rest: `content`, `recurring`,
`interval`, `interval_number`, `interval_unit`, `due`, `days_until_due`
(negative when overdue), `last_done`, `next_variant`, `note_id`, `list`.
Notes added in the app appear on the next poll, deleted ones disappear with
their device, an edited text renames the device and keeps the entity id.

The list sensors' `notes` attribute is a list of `{content, variant, due,
recurring}`, so a template can render the due notes:

```jinja
{% for note in state_attr('sensor.haushalt_due', 'notes') %}
- {{ note.content }}{% if note.variant %} · {{ note.variant }}{% endif %}
{% endfor %}
```

Counts measure calendar days in Home Assistant's time zone and roll over at
midnight without waiting for the next poll.

## Development

```
uv venv .venv --python 3.14
uv pip install --python .venv/bin/python homeassistant==2026.10.2 pytest-homeassistant-custom-component==0.13.373 ruff
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

`scripts/release.sh 0.1.1` bumps the version, pushes, waits for the Validate
workflow and publishes the GitHub release HACS picks up.

## Later

- Marking a note as done from Home Assistant (a second function that stamps
  the app's clocks so phones merge it).
- Push instead of polling.
