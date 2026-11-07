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
| `POST /activity-drafts/public-speaking` | `city`, `submissionDate`, `eventFormat` |
| `POST /activity-drafts/workshop` | `city`, `submissionDate`, `durationHours` |
| `POST /activity-drafts/*` (all) | `submissionDate` (set automatically) |
| `PATCH /activities/{id}` | Expects `{"data": {...}}` wrapper |

Other limits:
- `description` (rendered HTML) is capped at **2000 characters**: the
  interactive flow warns before submitting, and `submit --file` refuses to send

Fields that must be completed via the Advocu web panel:
- **City** — requires geocoded autocomplete
- **Image** — file upload (no API endpoint for GDE accounts)

If you discover new API behaviour, please open an issue or PR updating
this list and the relevant code comments.

## Adding a new draft type

Per the Personal API docs (July 2026), a few draft endpoints are not covered
yet: `interaction-with-googlers`, `mentoring` and `product-feedback-given`.
To add one:

1. `api.py`: add `create_<type>_draft()`, posting to `/activity-drafts/<endpoint>`.
2. `templates.py`: add the type to `_SPECS` (required keys, optional keys with
   their defaults) and the branch in `payload_from_spec()` that builds the API
   payload. Then add a `build_<type>()` that asks the questions and ends with
   `_finish()`.
3. `cli.py`: add the builder and the client method name to `_SUBMITTERS`, and a
   `submit <type>` command like the existing ones.
4. `examples/<type>.toml` (or `.json`): a template for `submit --file`. A test
   loads every file in `examples/`, so it cannot go stale. Add the type to
   `test_there_is_an_example_for_each_draft_type` too.
5. Tests for the payload (`tests/test_payloads.py`) and the command
   (`tests/test_cli.py`).
6. Try it against the real API and record any field it rejects in the tables
   above, with the exact error.

## Code style

- Python 3.11+, type hints with `from __future__ import annotations`
- Keep prompts in English (the tool targets the global GDE community)
- No external dependencies beyond `click`, `requests`, and `rich`

## Questions?

Open an issue — we're happy to help.
