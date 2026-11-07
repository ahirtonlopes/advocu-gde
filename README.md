# advocu-gde

[![CI](https://github.com/ahirtonlopes/advocu-gde/actions/workflows/ci.yml/badge.svg)](https://github.com/ahirtonlopes/advocu-gde/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

> A CLI tool for Google Developer Experts to manage [Advocu](https://advocu.com) activities via the Personal API.

If you're a GDE, you know the drill: after every talk, workshop, article, or community event, you need to log your activity on Advocu. This tool lets you do that directly from your terminal — no more clicking through forms for every submission.

---

## Quick start

```bash
git clone https://github.com/ahirtonlopes/advocu-gde.git && cd advocu-gde
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Get your token: advocu.com → Profile → Settings → Personal API
export ADVOCU_TOKEN=your_personal_api_token_here

advocu submit talk
```

That's it — see [How submissions work](#how-submissions-work-important--read-this-first) for what happens next, or the sections below for everything else this tool can do.

---

## Contents

- [What this tool does](#what-this-tool-does)
- [Who is this for?](#who-is-this-for)
- [Getting your API token](#getting-your-api-token)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [How submissions work](#how-submissions-work-important--read-this-first)
- [Commands](#commands)
- [Markdown reference for descriptions](#markdown-reference-for-descriptions)
- [Submit from a file](#submit-from-a-file-non-interactive)
- [Batch submissions via script](#batch-submissions-via-script)
- [Identify your activity IDs](#identify-your-activity-ids)
- [Project structure](#project-structure)
- [Rate limiting](#rate-limiting)
- [Errors and timeouts](#errors-and-timeouts)
- [Known API limitations](#known-api-limitations)
- [Keeping up with the API](#keeping-up-with-the-api)
- [Contributing](#contributing)
- [License](#license)

---

## What this tool does

- **Lists** all your submitted activities with automatic pagination
- **Submits** drafts for all seven activity types the Personal API offers: talks, workshops, content (articles, videos, podcasts, books, newsletters, demos), stories, interactions with Googlers, product feedback and mentoring
- **Updates** existing activities via PATCH (fix titles, dates, URLs)
- **Converts Markdown to HTML** automatically — paste your LinkedIn post or event notes and the tool formats it correctly for Advocu's editor, including clickable links for slides, codelabs, and repositories

---

## Who is this for?

Any active GDE who wants a faster way to submit activities to Advocu. It works regardless of your GDE track — AI, Android, Flutter, Firebase, Angular, Web, Go, Kotlin, and more.

The tool is intentionally generic. There are no personal defaults baked in — every GDE configures it with their own token and fills in their own data.

---

## Getting your API token

1. Log in to [advocu.com](https://advocu.com)
2. Go to your **Profile → Settings → Personal API**
3. Generate or copy your **Personal API token**
4. Keep it safe — treat it like a password

---

## Requirements

- Python 3.11 or higher
- A valid Advocu Personal API token

---

## Installation

```bash
git clone https://github.com/ahirtonlopes/advocu-gde.git
cd advocu-gde

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -e .
```

Verify the installation:

```bash
advocu --help
```

---

## Configuration

Set your token as an environment variable before running any command:

```bash
export ADVOCU_TOKEN=your_personal_api_token_here
```

To avoid setting it every session, add it to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
echo 'export ADVOCU_TOKEN=your_personal_api_token_here' >> ~/.zshrc
source ~/.zshrc
```

Or use a `.env` file (never commit this file):

```bash
cp .env.example .env
# open .env and fill in your token
source .env
```

You can also pass the token inline for a one-off command:

```bash
advocu --token YOUR_TOKEN list
```

---

## How submissions work (important — read this first)

The Advocu Personal API **creates drafts**, not published activities. Think of it as pre-filling the form for you. The full flow is:

```
advocu submit talk|workshop|content|story|interaction|feedback|mentoring
        ↓
  Draft created via API with:
    title, date, URL, description (HTML with links), tags, metrics, country
        ↓
  Open the Advocu web panel
        ↓
  Select your city (required — must use the autocomplete)
  Upload a cover image (required — no API endpoint for this)
  Review the text and formatting
  Click Publish
```

This is not a limitation of this tool — it reflects what the Advocu Personal API currently exposes. Fields like `city` and `imageUrl` require the web UI. Everything else can be submitted programmatically.

### What the API accepts

Every draft also takes `title`, `tags`, `private`, and a text field (`description`, or `whyIsSignificant` for stories). These are the fields each endpoint accepts besides those, checked against the live API on 2026-11-07:

| Command | Endpoint | Other fields |
|---|---|---|
| `talk` | `public-speaking` | `activityDate`, `activityUrl`, `metrics.attendees`, `inPersonAttendees`, `eventFormat`, `country`, `additionalInfo` |
| `workshop` | `workshop` | the same as `talk` |
| `content` | `content-creation` | `contentType`, `activityDate`, `activityUrl`, `metrics.readers`, `additionalInfo` |
| `story` | `stories` | `significanceType`, `activityUrl`, `metrics.impact`, `additionalInfo`. **No date** |
| `interaction` | `interaction-with-googlers` | `interactionType`, `format`, `activityDate`, `metrics.timeSpent`, `additionalLinks`, `additionalInfo` |
| `feedback` | `product-feedback-given` | `contentType`, `productDescription`, `activityDate`, `metrics.timeSpent`, `additionalInfo` |
| `mentoring` | `mentoring` | `activityDate`, `activityUrl`, `metrics.attendees`, `inPersonAttendees`, `eventFormat`, `country`, `additionalInfo` |

Metrics are whole numbers of **1 or more**: the API refuses `0`, so leave a metric out when you do not know it (the CLI does this for you when you answer `0` to skip).

### What must be done manually in the web panel

| Field | Why |
|---|---|
| `city` | Requires Google Places geocoded autocomplete — plain text is rejected |
| Cover image | File upload — not available via Personal API |
| `submissionDate` | Set automatically by the API to the current timestamp |

---

## Commands

`advocu --version` prints the installed version. Every `advocu submit ...` command can also read the draft from a file instead of asking questions: see [Submit from a file](#submit-from-a-file-non-interactive).

### `advocu list` — List all your activities

Fetches every page automatically and displays a formatted table with ID, type, title, dates, and status.

```bash
advocu list

# Export everything as JSON (useful for scripting)
advocu list --json-out
advocu list --json-out > my-activities.json
```

---

### `advocu recent [N]` — See your most recent activities

Shows the N most recent activities sorted by event date.

```bash
advocu recent          # 10 most recent (default)
advocu recent 20       # 20 most recent
advocu recent 5 --json-out
```

---

### `advocu submit talk` — Submit a talk draft

Walks you through a short form. The most important part is the description — paste your LinkedIn post, event recap, or notes directly. The tool converts Markdown formatting and links to proper HTML.

```bash
advocu submit talk
```

**Example session:**

```
🎤  New talk (public-speaking)

Your role at the event [Speaker]:
Talk title: Real World Design with Agent Development Kit (ADK)
Event name: Google I/O Extended São Paulo
Activity date (YYYY-MM-DD): 2024-06-20
Event URL: https://gdg.community.dev/events/details/google-...
Number of attendees (approx.) (0 to skip) [0]: 150
Event format (In-Person, Virtual, Hybrid) [In-Person]:
Language [EN-US]: PT-BR
Country: Brazil
Tags: AI, AI - Agent Development Kit (ADK), AI - Gemini

Descriptive text (post, notes, summary):
  Supports Markdown: **bold**, [text](url), * list item, → item
  Paste your text and press Enter twice on a blank line to finish:

Had an amazing session at Google I/O Extended today!

**What I covered:**

* Why ADK changes the way we design AI agents
* Moving from text generators to systems that truly perceive, plan, and act
* [SequentialAgent, ParallelAgent, LoopAgent](https://google.github.io/adk-docs/) in production


Resources (slides, codelab, GitHub, etc.) — blank name to finish:
  Resource name: Slides
  URL: https://speakerdeck.com/ahirtonlopes/...
  Resource name: Codelab
  URL: https://codelabs.developers.google.com/...
  Resource name: GitHub
  URL: https://github.com/ahirtonlopes/real-world-adk
  Resource name: [Enter]
```

**The title is auto-formatted** as: `{Role} @ {Event} - {Talk Title} ({Language})`

Example: `Speaker @ Google I/O Extended São Paulo - Real World Design with ADK (PT-BR)`

After sending, you'll see the draft ID and the steps to complete it in the web panel.

---

### `advocu submit workshop` — Submit a workshop draft

Same flow as a talk. The event format defaults to `In-Person`.

```bash
advocu submit workshop
```

---

### `advocu submit content` — Submit a content activity

For articles, videos, podcasts and more. Asks for content type, publication date, URL, and view/reader count.

```bash
advocu submit content
```

Content types: `Articles`, `Videos`, `Podcasts`, `Books`, `Newsletters`, `Demos`

**Example:**

```
📝  New content (content-creation)

Content type [Articles]: Videos
Title: Introduction to Gemini API — Getting Started
Publication date (YYYY-MM-DD): 2024-05-10
Content URL: https://youtube.com/watch?v=...
Language [EN-US]:
Views / readers (approx.) (0 to skip) [0]: 3500
Tags: AI, AI - Gemini
```

---

### `advocu submit story` — Submit a story draft

```bash
advocu submit story
```

Stories have no date in the API. The text you write is Advocu's "Why is this significant?" field, and you can set the significance (`Community Leading`, `Social Impact`, ...) and how many people it reached.

---

### `advocu submit interaction` - Interactions with Googlers

Sessions with Google product teams: councils, feedback sessions, training seminars. Asks for the interaction type, the format and the time spent in minutes.

```bash
advocu submit interaction
```

The title becomes `Title @ Event (LANG)` when you name an event.

---

### `advocu submit feedback` - Product feedback given to Google

Feedback sessions and early access programs. Asks for the type, a short description of the product (up to 500 characters) and the time spent in minutes.

```bash
advocu submit feedback
```

---

### `advocu submit mentoring` - Mentoring

```bash
advocu submit mentoring
```

Asks for how many people you mentored and the event format, with the country for in-person and hybrid mentoring.

---

### `advocu update <activityId>` — Update an existing activity

Use the full `activityId` (visible with `advocu recent --json-out`).

```bash
# Fix a title
advocu update 6a046eaec29257fb76a2b8e7 -f title="Corrected Title (EN-US)"

# Fix multiple fields at once
advocu update 6a046eaec29257fb76a2b8e7 \
  -f activityDate=2024-03-10 \
  -f activityUrl=https://new-url.com

# JSON payload for nested or complex updates
advocu update 6a046eaec29257fb76a2b8e7 \
  --json-payload '{"title": "New Title", "attendees": 200}'
```

---

### `advocu fix-date <activityId> <YYYY-MM-DD>` — Fix a date quickly

Shortcut for correcting activity or submission dates without typing the full update command.

```bash
# Fix the activity date (default)
advocu fix-date 6a046eaec29257fb76a2b8e7 2024-03-15

# Fix the submission date
advocu fix-date 6a046eaec29257fb76a2b8e7 2024-03-15 --field submissionDate
```

---

## Markdown reference for descriptions

When filling in the description field, you can use:

| Markdown | Result in Advocu |
|---|---|
| `**text**` | **Bold** |
| `_text_` | _Italic_ |
| `[label](https://url)` | Clickable link |
| `* item` or `→ item` | Bullet list item |
| Blank line | New paragraph |

Underscores inside words are left as typed, so identifiers such as `exit_loop` or `before_tool_callback` are safe to write in a technical description. `_italic_` only works around whole words.

**Example input:**

```
I presented at the GDG DevFest this year.

**Topics covered:**

* Introduction to Gemini API
* [Function Calling demo](https://github.com/my/demo)
* Real-world use cases in enterprise

The room was packed with 200+ developers asking great questions.
```

**Becomes in Advocu:**

```html
<p>I presented at the GDG DevFest this year.</p>
<p></p>
<p><strong>Topics covered:</strong></p>
<ul>
 <li>Introduction to Gemini API</li>
 <li><a href="https://github.com/my/demo" rel="nofollow">Function Calling demo</a></li>
 <li>Real-world use cases in enterprise</li>
</ul>
<p></p>
<p>The room was packed with 200+ developers asking great questions.</p>
```

---

## Submit from a file (non-interactive)

Write the draft once in a `.toml` or `.json` file and send it with one command, no prompts. It suits writing the text in your own editor, keeping drafts in git, or sending several at once. Ready-to-copy templates for each type live in [`examples/`](examples/).

```bash
advocu submit talk --file examples/talk.toml --dry-run   # validate and preview, send nothing
advocu submit talk --file examples/talk.toml             # preview, then ask to confirm
advocu submit talk --file examples/talk.toml --yes       # send without asking (for scripts)
```

`--dry-run` needs no token and no network, so it is safe to run anywhere, CI included. Without `--yes` you are asked to confirm, because a draft cannot be deleted through the API.

A talk, in TOML:

```toml
title = "Building Agents with Google ADK"
event = "DevFest Example City 2026"
date = 2026-10-31
url = "https://gdg.community.dev/events/details/example-devfest/"
attendees = 120
event_format = "In-Person"
language = "PT-BR"
country = "Brazil"
tags = ["AI", "AI - Agent Development Kit (ADK)", "AI - Gemini"]
description = """
On October 31, 2026, I delivered the session at DevFest Example City 2026.

* Custom tools, with exit_loop-style stop conditions;
* A live demo on [Colab](https://colab.research.google.com/github/example/demo).
"""

[[resources]]
name = "Slides"
url = "https://example.com/slides.pdf"
```

| Key | Used by | Default | Notes |
|---|---|---|---|
| `title` | all | required | Final title: `Role @ Event - Title (LANG)` for talks and workshops, `Title @ Event (LANG)` for interactions, `Title (LANG)` for the rest (stories keep it as written) |
| `event` | talk, workshop (required), interaction | - | Event name |
| `date` | all except story | required | `YYYY-MM-DD`, quoted or as a native TOML date. Stories have no date |
| `url` | talk, workshop, content (required), story, mentoring | - | `http://` or `https://` |
| `tags` | all | required | List of text; the built-in list is in `templates.py` |
| `description` | all | empty | Markdown, see [the reference](#markdown-reference-for-descriptions). For stories it fills "Why is this significant?" |
| `additional_info` | all | - | Plain text, up to 2000 characters |
| `resources` | all except story | - | List of `{name, url}`, appended as a "Resources" list |
| `role` | talk, workshop | `Speaker`, `Workshop Proctor` | |
| `language` | all except story | `EN-US` | EN-US, PT-BR, ES, FR, DE, JA, KO, ZH. The language the material is delivered in |
| `attendees` | talk, workshop, mentoring | left out | Whole number, 1 or more (people mentored, for mentoring) |
| `in_person_attendees` | talk, workshop, mentoring | left out | 0 or more. For hybrid events: how many were in the room |
| `readers` | content | left out | Views or readers, 1 or more |
| `minutes` | interaction, feedback | left out | Time spent, whole minutes, 1 or more |
| `impact` | story | left out | People reached, 1 or more |
| `country` | talk, workshop, mentoring | left out | The city is set later in the web panel |
| `event_format` | talk, workshop, mentoring | workshop: `In-Person`; others left out | In-Person, Virtual or Hybrid |
| `content_type` | content, feedback | `Articles`, `Product feedback session` | content: Articles, Videos, Podcasts, Books, Newsletters, Demos. feedback: Early access program, Product feedback session |
| `interaction_type` | interaction | required | Product feedback (research studies, roadmap input, Customer Advisory Boards, EAP); File bugs / help out with finding bugs; GitHub; Stack Overflow; Industry; Other interactions with Google Product Teams |
| `format` | interaction | required | Survey; Video feedback; In-person feedback sessions; Online feedback sessions; Feedback summits; User study / focus group; Feedback submissions; Other |
| `additional_links` | interaction | - | Text |
| `product_description` | feedback | required | Markdown, up to 500 characters once rendered |
| `significance_type` | story | left out | Diversity & Inclusion; Helping Business; Social Impact; Feedback to Google; Community Leading; Technology / Open source |

What the CLI checks before sending anything:

- **Every problem is listed at once**, so you fix the file in a single pass. A misspelled key (`atendees`) is reported with the list of allowed keys instead of being ignored.
- **A text over the API's limits blocks the submission** (description 2000 characters, title 3 to 200, product description 500; see [Known API limitations](#known-api-limitations)); with `--dry-run` it fails too, which makes it usable as a check in CI.
- **A tag that is not in the built-in list only warns.** Advocu changes its tags without notice, so the CLI does not refuse them; the API has the last word. Hybrid and in-person events without a country, or with more people in the room than in total, also only warn.
- **Allowed values are checked** (`event_format`, `content_type`, `format`, ...) and the error lists the valid ones.

Exit codes: `0` sent, or a dry run that passed; `1` invalid draft, or an error from the API or the network; `2` wrong command-line usage (for example a file that does not exist).

---

## Batch submissions via script

Put one file per activity in a folder and loop over them:

```bash
for f in drafts/talk-*.toml; do
  advocu submit talk --file "$f" --yes
done
```

The client waits 2 seconds between calls (the API allows 30 requests per minute), so a long list just takes a little longer.

From Python, build the payload with the same function the CLI uses, so validation and the Markdown conversion stay identical:

```python
from advocu_manager.api import AdvocuClient
from advocu_manager.templates import SpecError, payload_from_spec

client = AdvocuClient()  # reads ADVOCU_TOKEN from the environment

talks = [
    {
        "title": "Intro to ADK",
        "event": "DevFest Berlin",
        "date": "2024-11-10",
        "url": "https://devfest.berlin",
        "attendees": 300,
        "country": "Germany",
        "tags": ["AI", "AI - Agent Development Kit (ADK)"],
        "description": "Talk about the Agent Development Kit.\n\n* ADK architecture\n* [Live demo](https://github.com/my/demo)",
        "resources": [{"name": "Slides", "url": "https://speakerdeck.com/example"}],
    },
    {
        "title": "Gemini in Production",
        "event": "GDG London",
        "date": "2024-11-22",
        "url": "https://gdg.community.dev/gdg-london",
        "attendees": 120,
        "country": "United Kingdom",
        "tags": ["AI", "AI - Gemini"],
        "description": "Session on deploying Gemini-powered apps.",
    },
]

for spec in talks:
    try:
        result = client.create_talk_draft(payload_from_spec("talk", spec))
    except SpecError as e:
        print("Skipped:", "; ".join(e.errors))
        continue
    print(f"Draft created: {result.get('id')} - {spec['title']}")
```

---

## Identify your activity IDs

To get the full `activityId` needed for `update` and `fix-date`:

```bash
# Inspect recent activities as JSON
advocu recent 10 --json-out | python3 -c "
import json, sys
for a in json.load(sys.stdin):
    print(a.get('activityId'), a.get('data',{}).get('activityDate'), a.get('data',{}).get('title','')[:60])
"
```

---

## Project structure

```
advocu-gde/
├── advocu_manager/
│   ├── __init__.py       # Package version (single source of truth)
│   ├── api.py            # HTTP client: rate limiting, timeouts, error messages
│   ├── cli.py            # Click CLI commands
│   └── templates.py      # Draft specs, validation, prompts, Markdown→HTML converter
├── examples/             # Ready-to-copy draft files for `submit --file` (tested)
├── tools/check_api.py    # Compares this project with the live API (see below)
├── tests/                # pytest suite (parser, client, drafts, CLI, checker)
├── .github/workflows/    # CI — runs the test suite on every push/PR
├── pyproject.toml
├── requirements.txt
├── LICENSE               # MIT
├── CONTRIBUTING.md
├── .env.example
└── README.md
```

---

## Rate limiting

The Advocu API allows **30 requests per minute**. The client automatically throttles (2 seconds between calls). Fetching a large list of activities may take a few seconds — this is expected and handled transparently.

---

## Errors and timeouts

Requests time out after 5 seconds to connect and 30 seconds to read, so a dead connection ends with a message instead of hanging the terminal. Failures are reported on one line, with exit code `1`, rather than as a traceback:

```
Error: HTTP 401: check that your token is valid: set ADVOCU_TOKEN or pass --token
Error: Could not connect to Advocu (api.advocu.com). Check your internet connection and try again.
Error: HTTP 400: Activity draft did not pass validation. [#: extraneous key [durationHours] is not permitted]
```

For a rejected draft, the part in brackets is what Advocu says is wrong, which is usually enough to fix the file.

---

## Known API limitations

Discovered through live testing; Advocu does not document them. Last checked against the API on **2026-11-07**.

- `submissionDate` cannot be set (it is assigned automatically)
- `city` is validated against Google Places and cannot be sent as free text
- `imageUrl`: images are uploaded in the web panel, there is no API for it
- `durationHours` is rejected on every endpoint
- Stories take no date (`activityDate` is rejected); their text is `whyIsSignificant`
- Metrics (`attendees`, `readers`, `timeSpent`, `impact`, `minutes`) must be whole numbers of 1 or more. `0` is rejected with `0 is not greater or equal to 1`, so leave the metric out instead
- Text limits: `title` 3 to 200 characters; `description`, `whyIsSignificant` and `additionalInfo` 2000; `productDescription` 500. The description limit counts the rendered HTML, tags included
- Enum values (`eventFormat`, `contentType`, `format`, `interactionType`, `significanceType`) and tags are closed lists: anything else gets `is not a valid enum value`. Advocu has changed the tags before (the Cloud tags were reorganised between September and November 2026)
- `eventFormat` used to be rejected on talks and is accepted now; `inPersonAttendees` goes with it
- **An empty draft is accepted** (HTTP 201), so a draft endpoint cannot be probed with an empty body: it leaves an empty draft in the account
- PATCH requests are handled automatically by the CLI: fields are wrapped in `{"data": {...}}` internally

If you discover new API behaviour, please [open an issue](https://github.com/ahirtonlopes/advocu-gde/issues) or contribute to [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Keeping up with the API

Advocu changes tags, allowed values and rules without notice, and a list copied once goes stale. `tools/check_api.py` asks the live API what it accepts and reports what no longer matches this project:

```bash
ADVOCU_TOKEN=... python tools/check_api.py
```

It checks every built-in tag, every allowed value, each file in `examples/` exactly as the CLI would send it, and the size and metric limits. It cannot discover *new* tags or values (the API does not list them); for those, compare with the tag dropdown in the web panel.

It never creates a draft. Each request carries two deliberate violations (a key that does not exist and a value of the wrong type), so the API always answers 400 with the full list of problems, and the script reports only the ones that are not deliberate. If a request is ever accepted, it stops at once and prints the draft id. Exit codes: `0` no drift, `1` drift found, `2` a draft was created by mistake, `3` the check could not finish.

---

## Contributing

Contributions are welcome from any GDE. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started.

## License

[MIT](LICENSE) — free to use, fork, and share.
