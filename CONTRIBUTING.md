# Contributing to advocu-gde

Thank you for your interest in contributing! This project exists to help
Google Developer Experts manage their Advocu activities more efficiently.
Every GDE is welcome to contribute.

## How to contribute

1. **Fork** the repository and create a branch from `main`
2. **Install** in development mode:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```
3. **Make your changes** — keep them focused and well-described
4. **Test manually** with your own `ADVOCU_TOKEN` before submitting
5. Open a **Pull Request** with a clear description of what changed and why

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
| `POST /activity-drafts/workshop` | `city`, `submissionDate` |
| `POST /activity-drafts/*` (all) | `submissionDate` (set automatically) |
| `PATCH /activities/{id}` | Expects `{"data": {...}}` wrapper |

Fields that must be completed via the Advocu web panel:
- **City** — requires geocoded autocomplete
- **Image** — file upload (no API endpoint for GDE accounts)

If you discover new API behaviour, please open an issue or PR updating
this list and the relevant code comments.

## Code style

- Python 3.11+, type hints with `from __future__ import annotations`
- Keep prompts in English (the tool targets the global GDE community)
- No external dependencies beyond `click`, `requests`, and `rich`

## Questions?

Open an issue — we're happy to help.
