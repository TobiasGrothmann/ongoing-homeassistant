# Ongoing → Home Assistant integration (read-only, v1)

## Context

Ongoing (Android, Flutter) keeps recurring tasks; groups share notes through Firestore under `groups/<key>/notes`. Tobias wants the shared group state in Home Assistant 2026.10 so it can sit on dashboards and drive automations (e.g. the TRMNL display).

Decisions taken 2026-10-25:
- **Code lives in a sibling repo** `~/projects/flutter/ongoing-homeassistant`, same layout as `~/projects/trmnl/terminus_homeassistant` (HACS-installable custom repository, SSH deploy script).
- **Access path: Cloud Function endpoint** keyed by the group key. HA polls JSON; no Firebase auth in Python; HA never becomes a group member.
- **Scope v1: read-only.** "Did it" from HA is a later step (second function stamping HLC clocks).

Test group: a shared list with one note; its key stays out of this repo.

## Part 1 — backend: `groupNotes` HTTPS function (app repo)

File: `~/projects/flutter/ongoing/functions/src/index.ts`, branch `feat/ha-group-endpoint` off `main` (never commit to `main`; stage explicit paths).

- `export const groupNotes = onRequest({ region: "us-central1", cors: false }, …)`
- Auth: `X-Group-Key: <groupKey>` header (Cloud Run swallows bearer tokens); malformed or unknown → 401. Key never in the URL.
- Read `groups/<key>`; missing → 404. Read `notes` subcollection, drop docs with `deletedAt != null`.
- Response (JSON):
  ```json
  { "group": { "key": "…", "name": "…" },
    "notes": [ { "id", "content", "due": "YYYY-MM-DD", "lastDone": ISO|null,
                 "isRecurring", "durationType", "durationNumber",
                 "nextVariant": "name or \"\"" } ],
    "serverTime": ISO }
  ```
  - `due` comes from the stored ISO string (`dateTimeFromAny` semantics: string or Timestamp), truncated to the calendar date.
  - `nextVariant` mirrors `Note.getNextVariantName()` in `lib/model/note.dart:298`: empty unless recurring and variations non-empty; `rotatingVariations[nextRotatingVariationIndex % len].name`.
  - Parse defensively per doc (skip and log an unreadable one, like S5).
- Check: `cd functions && npx tsc --noEmit -p .`. Deploy: user runs `firebase deploy --only functions`.
- Update `REVIEW.md` Done section; note the endpoint in `CLAUDE.md` "Backend" line.
- Guardrail (document in REVIEW.md decisions): the endpoint makes a key readable without the app. Same trust model as join-by-key (B2); keys stay out of URLs and logs.

## Part 2 — integration repo `~/projects/flutter/ongoing-homeassistant`

Copy the skeleton from the TRMNL repo (`pyproject.toml`, `hacs.json`, `scripts/deploy.sh`, `scripts/release.sh`, test scaffolding, `.gitignore`, LICENSE) and adapt names. `git init`, first commit on `main`.

```
custom_components/ongoing/
  manifest.json      domain "ongoing", iot_class cloud_polling, integration_type service, requirements []
  const.py           DOMAIN, DEFAULT_SCAN_INTERVAL=2 min, ENDPOINT_URL, CONF_GROUP_KEY
  api.py             OngoingClient(session, group_key): async fetch() -> GroupData; errors: OngoingAuthError (401/404), OngoingError
  coordinator.py     DataUpdateCoordinator[GroupData]; UpdateFailed on OngoingError, ConfigEntryAuthFailed on 404 (group gone)
  config_flow.py     step user: group key (TextSelector, password type); validates by calling fetch(); unique_id = group key; title = group name. Reauth/reconfigure: re-enter key.
  __init__.py        setup/unload, PLATFORMS = [todo, sensor]
  entity.py          base entity with DeviceInfo per group (identifiers {(DOMAIN, key)}, name = group name)
  todo.py            one TodoListEntity per group, supported_features = 0 (read-only); items: uid = note id, summary = content (+ " · nextVariant" when set), due = date, status NEEDS_ACTION; sorted by due then content (same as widget)
  sensor.py          due_today (count, due <= today), overdue (count, due < today), next_due (date), total (count)
  diagnostics.py     redact group key
  strings.json + translations/en.json, de.json
  icons.json
```

- Date math: compare calendar dates in HA's configured time zone (`dt_util.now().date()`), never hours (D1 lesson).
- No network in `__init__` beyond the coordinator's first refresh; endpoint URL as a constant, overridable through an advanced option only if needed later.

Tests (`tests/`, pytest-homeassistant-custom-component, as in TRMNL): `test_api.py` with a fixture JSON copied from a real response, `test_config_flow.py` (ok, 401, 404, network error), `test_todo.py`, `test_sensor.py`. Keep them few and precise.

README: why, install (HACS custom repo + manual), setup (group key from the app's Sharing page), entities, polling interval, privacy note (HA only ever sends the group key to the function).

## Verification

1. Function: `npx tsc --noEmit`; after deploy, `curl -H "X-Group-Key: <key>" https://us-central1-ongoing-34fe1.cloudfunctions.net/groupNotes` returns the one note; a wrong key gives 401.
2. Integration: `pytest` green, `ruff check` clean.
3. Deploy with `HA_SSH_HOST=… scripts/deploy.sh`, add the integration via UI with the test key, confirm `todo.<group>` lists the note and the sensors match; check via ha-mcp `ha_get_state`.
4. Edit the note's due date on the phone, wait one poll, confirm HA follows.

## Later (not in v1)
- `completeNote` function with HLC stamping (clock node `ha-<uuid>`), todo `update_item` → "did it".
- Push to HA via webhook from `onNoteChange` if polling ever feels slow.

---

# Phase 2 — one device per note (decided 2026-10-25)

Why devices: a device can be assigned to an area and pinned on dashboards; "did it" from HA is dropped, read-only stays.

- **Device per note**, identifiers `(ongoing, <note id>)`, `via_device` the list device, name = note text, model = the interval ("once", "every week", "every 2 weeks"). Created, renamed and removed by the coordinator on every poll; the list device is created there too so `via_device` resolves.
- **Two entities per note**, unique ids `<note id>_due` and `<note id>_due_date`:
  - `binary_sensor.<note>`: on when due today or earlier. Attributes: `content`, `recurring`, `interval`, `interval_number`, `interval_unit`, `due`, `days_until_due` (negative when overdue), `last_done`, `next_variant`, `note_id`, `list`.
  - `sensor.<note>_due_date`: device class date.
- Entities for new notes are added by a coordinator listener; removing the device removes its entities. Content edits rename the device, the entity id stays.
- Display is decided later: a dashboard with all notes, chosen notes on the TRMNL, notes mapped to areas. The list-level entities from phase 1 stay.
