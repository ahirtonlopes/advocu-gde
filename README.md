# advocu-gde

> A CLI tool for Google Developer Experts to manage [Advocu](https://advocu.com) activities via the Personal API.

If you're a GDE, you know the drill: after every talk, workshop, article, or community event, you need to log your activity on Advocu. This tool lets you do that directly from your terminal — no more clicking through forms for every submission.

---

## What this tool does

- **Lists** all your submitted activities with automatic pagination
- **Submits** drafts for talks, workshops, content (articles/videos/podcasts), and stories
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
advocu submit talk|workshop|content|story
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

| Field | talk | workshop | content | story |
|---|---|---|---|---|
| `title` | ✅ | ✅ | ✅ | ✅ |
| `activityDate` | ✅ | ✅ | ✅ | ✅ |
| `activityUrl` | ✅ | ✅ | ✅ | ✅ |
| `description` (HTML) | ✅ | ✅ | ✅ | ✅ |
| `tags` | ✅ | ✅ | ✅ | ✅ |
| `metrics` (attendees/readers) | ✅ | ✅ | ✅ | ✅ |
| `country` | ✅ | ✅ | — | — |
| `eventFormat` | ❌ | ✅ | — | — |

### What must be done manually in the web panel

| Field | Why |
|---|---|
| `city` | Requires Google Places geocoded autocomplete — plain text is rejected |
| Cover image | File upload — not available via Personal API |
| `submissionDate` | Set automatically by the API to the current timestamp |

---

## Commands

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
Number of attendees (approx.) [0]: 150
Language [EN-US]: PT-BR
Country: Brazil
Tags: AI, AI - Agents, AI - Agent Development Kit (ADK)

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

Same flow as a talk, with two extra fields: event format and duration in hours.

```bash
advocu submit workshop
```

---

### `advocu submit content` — Submit a content activity

For articles, videos, and podcasts. Asks for content type, publication date, URL, and view/reader count.

```bash
advocu submit content
```

Content types: `Articles`, `Videos`, `Podcasts`, `Other`

**Example:**

```
📝  New content (content-creation)

Content type [Articles]: Videos
Title: Introduction to Gemini API — Getting Started
Publication date (YYYY-MM-DD): 2024-05-10
Content URL: https://youtube.com/watch?v=...
Language [EN-US]:
Views / readers (approx.) [0]: 3500
Tags: AI, AI - Gemini
```

---

### `advocu submit story` — Submit a story draft

```bash
advocu submit story
```

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

## Batch submissions via script

If you have multiple activities to submit at once, you can use the Python API directly:

```python
from advocu_manager.api import AdvocuClient
from advocu_manager.templates import _md_to_html, _build_resources_html

client = AdvocuClient()  # reads ADVOCU_TOKEN from environment

talks = [
    {
        "title": "Speaker @ DevFest Berlin - Intro to ADK (EN-US)",
        "activityDate": "2024-11-10",
        "activityUrl": "https://devfest.berlin",
        "description": _md_to_html(
            "Talk about the Agent Development Kit at DevFest Berlin.\n\n"
            "* ADK architecture\n"
            "* [Live demo](https://github.com/my/demo)\n"
            "* Q&A highlights"
        ) + _build_resources_html([
            ("Slides", "https://speakerdeck.com/..."),
            ("GitHub", "https://github.com/..."),
        ]),
        "tags": ["AI", "AI - Agents"],
        "metrics": {"attendees": 300},
        "country": "Germany",
        "private": False,
    },
    {
        "title": "Speaker @ GDG London - Gemini in Production (EN-US)",
        "activityDate": "2024-11-22",
        "activityUrl": "https://gdg.community.dev/gdg-london",
        "description": _md_to_html("Session on deploying Gemini-powered apps."),
        "tags": ["AI", "AI - Gemini"],
        "metrics": {"attendees": 120},
        "country": "United Kingdom",
        "private": False,
    },
]

for talk in talks:
    result = client.create_talk_draft(talk)
    print(f"Draft created: {result.get('id')} — {talk['title'][:60]}")
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
│   ├── __init__.py       # Package version
│   ├── api.py            # HTTP client with rate limiting (30 req/min)
│   ├── cli.py            # Click CLI commands
│   └── templates.py      # Interactive forms + Markdown→HTML converter
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

## Known API limitations

These were discovered through live testing and are not officially documented by Advocu:

- `submissionDate` cannot be set via POST (it's assigned automatically)
- `city` is validated against Google Places and cannot be sent as free text
- Image upload is not available via the Personal API for GDE accounts
- `eventFormat` is accepted by `/activity-drafts/workshop` but rejected by `/activity-drafts/public-speaking`
- PATCH requests require fields to be wrapped in `{"data": {...}}`

If you discover new API behaviour, please [open an issue](https://github.com/ahirtonlopes/advocu-gde/issues) or contribute to [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Contributing

Contributions are welcome from any GDE. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started.

## License

[MIT](LICENSE) — free to use, fork, and share.
