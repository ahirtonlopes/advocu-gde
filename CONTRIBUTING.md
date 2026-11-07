# Contributing to advocu-gde

Thank you for your interest in contributing! This project exists to help
Google Developer Experts manage their Advocu activities more efficiently.
Every GDE is welcome to contribute.

## How to contribute

1. **Fork** the repository and create a branch from `main`
2. **Install** in development mode, with test dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
3. **Make your changes** — keep them focused and well-described
4. **Run the test suite**:
   ```bash
   pytest -v
   ```
   Add tests for any new behaviour, especially API quirks discovered through
   live testing (see [Code style](#code-style) below).
5. **Test manually** with your own `ADVOCU_TOKEN` before submitting
6. Open a **Pull Request** with a clear description of what changed and why — CI runs the test suite automatically on every PR

## What we welcome

- Bug fixes (especially API behaviour discoveries)
- New activity types as Advocu adds them to the Personal API
- Improved prompts or UX tweaks
- Better documentation or usage examples
- Translations of the README

## API behaviour notes

These were discovered through live testing and are not officially documented:

| Endpoint | Rejected fields |
|---|---|
| `POST /activity-drafts/*` (all) | `submissionDate`, `imageUrl`, `city`, `durationHours` |
| `POST /activity-drafts/stories` | `activityDate` (stories have no date; the text is `whyIsSignificant`) |
| `POST /activity-drafts/interaction-with-googlers` | `activityUrl`, `country`, `eventFormat` |
| `POST /activity-drafts/product-feedback-given` | `activityUrl`, `country`, `eventFormat` |
| `PATCH /activities/{id}` | Expects `{"data": {...}}` wrapper |

Other rules, all measured against the live API:
- Metrics are whole numbers of **1 or more**: `0` is rejected, so a metric is left out when unknown
- `title` is 3 to 200 characters; `description`, `whyIsSignificant` and `additionalInfo` 2000; `productDescription` 500. The description limit counts the rendered HTML
- Tags and enum values are closed lists, and Advocu changes them without notice
- `eventFormat` used to be rejected on talks and is accepted now

Fields that must be completed via the Advocu web panel:
- **City** - requires geocoded autocomplete
- **Image** - file upload (no API endpoint for GDE accounts)

If you discover new API behaviour, please open an issue or PR updating
this list and the relevant code comments.

## Keeping the API knowledge honest

The notes above went stale once already, so they are checked rather than trusted:

```bash
ADVOCU_TOKEN=... python tools/check_api.py
```

Run it before a release and whenever a draft is rejected unexpectedly. It never
creates a draft: every request carries two deliberate violations, so the API
always answers 400 and lists what it dislikes. **Never probe a draft endpoint
with an empty or a valid payload**: the API accepts it (HTTP 201) and leaves a
draft in the account. When you write your own probe, keep both deliberate
violations, and treat any answer other than 400 as an error (a 429 has no
validation text, and reading it as "all clear" reports drift that is not there).

## Adding a new draft type

The CLI covers the seven draft endpoints the Personal API has today. If Advocu
adds another:

1. `api.py`: add `create_<type>_draft()`, posting to `/activity-drafts/<endpoint>`.
2. `templates.py`: add the type to `_SPECS` (required keys, optional keys with
   their defaults) and the branch in `payload_from_spec()` that builds the API
   payload. Then add a `build_<type>()` that asks the questions and ends with
   `_finish()`.
3. `cli.py`: add the builder and the client method name to `_SUBMITTERS`, and a
   `submit <type>` command like the existing ones.
4. `examples/<type>.toml` (or `.json`): a template for `submit --file`. A test
   loads every file in `examples/`, so it cannot go stale. Add the type to
   `KINDS` in `tests/test_payloads.py` too.
5. `tools/check_api.py`: add its endpoint to `ENDPOINTS` and any allowed-value
   list to `ENUMS`, then run it: the examples are sent exactly as the CLI would.
6. Tests for the payload (`tests/test_payloads.py`) and the command
   (`tests/test_cli.py`).
7. Record any field the API rejects in the tables above, with the exact error.

## Code style

- Python 3.11+, type hints with `from __future__ import annotations`
- Keep prompts in English (the tool targets the global GDE community)
- No external dependencies beyond `click`, `requests`, and `rich`

## Questions?

Open an issue — we're happy to help.
