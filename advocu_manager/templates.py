"""Draft payloads for each activity type: interactive prompts and file specs."""

from __future__ import annotations

import html
import json
import re
import sys
import tomllib
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import click
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

console = Console()

# Tags validated by the Advocu API — only values from this list are accepted.
# Using a tag outside this list will result in a 400 validation error.
# Last synced from the Advocu web UI tag dropdown (September 2026); every value was
# also checked against the API. Advocu retires and adds tags without notice, so
# re-sync when a draft is rejected with "is not a valid enum value".
SUGGESTED_TAGS = [
    # AI
    "AI",
    "AI - Agent Development Kit (ADK)",
    "AI - AI Studio",
    "AI - Antigravity",
    "AI - Colab",
    "AI - Gemini",
    "AI - Gemini Enterprise Agent Platform",
    "AI - Gemma",
    "AI - Genkit",
    "AI - JAX",
    "AI - Kaggle",
    "AI - Keras",
    "AI - LiteRT",
    "AI - MediaPipe",
    "AI - TorchTPU",
    "AI - TPU",
    "AI - vLLM",
    # Android
    "Android",
    "Android - Adaptive",
    "Android - Developer Productivity",
    "Android - Differentiated",
    "Android - Intelligent",
    # Cloud
    "Cloud - AI Tools",
    "Cloud - API Gateways",
    "Cloud - App Development",
    "Cloud - Compute, Networking, Storage",
    "Cloud - Data",
    "Cloud - Operations & Management",
    "Cloud - Security",
    "Cloud - Serverless & Containers",
    "Cloud Study Jam",
    # Firebase
    "Firebase",
    "Firebase - AI Logic",
    "Firebase - AI Monitoring",
    "Firebase - App Check",
    "Firebase - App Distribution",
    "Firebase - App Hosting",
    "Firebase - Authentication",
    "Firebase - Cloud Messaging",
    "Firebase - Crashlytics",
    "Firebase - Firestore",
    "Firebase - Functions",
    "Firebase - Performance",
    "Firebase - Realtime Database",
    "Firebase - Remote Config",
    "Firebase - SQL Connect",
    # Identity / Payments
    "Identity",
    "Identity - Google OAuth",
    "Identity - Sign in with Google",
    "Payments",
    "Payments - Google Pay",
    "Payments - Google Wallet",
    # Web / Workspace
    "Web",
    "Web - AI for Web Developers",
    "Web - Browser Extensions",
    "Web - CSS & UI",
    "Web - DevTools & Browser Automation",
    "Web - Fugu/PWA APIs",
    "Web - Identity",
    "Web - Performance",
    "Workspace - Add Ons",
    "Workspace - AppSheet",
    "Workspace - Google Apps Script",
    "Workspace - Google Workspace (REST) APIs",
    # Other
    "Angular",
    "AR/VR",
    "Build with AI",
    "Dart - Flutter",
    "DevFest",
    "Diversity & Inclusion",
    "Earth Engine",
    "Golang",
    "Google Cloud",
    "Google I/O Extended",
    "Google Maps Platform",
    "Google Workspace",
    "International Women's Day",
    "ML Study Jams",
    "Open Source",
    "Road to Google Developers Certification",
    "UX / UI Design",
]


# ── Markdown → HTML ──────────────────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    """Convert a subset of Markdown to HTML accepted by Advocu's editor."""
    lines = text.split("\n")
    html_parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("* ", "- ", "→ ", "• ")):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f" <li>{_inline(stripped[2:])}</li>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if stripped:
                html_parts.append(f"<p>{_inline(stripped)}</p>")
            else:
                html_parts.append("<p></p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _inline(text: str) -> str:
    # Escape & before inserting any HTML markup
    text = re.sub(r'&(?!(amp|lt|gt|quot|#\d+);)', '&amp;', text)

    # [text](url) → stash as a placeholder *before* bold/italic run, so a "_"
    # inside the URL (common in GitHub/Colab paths) can't be mistaken for an
    # italic delimiter and corrupt the href. Restored after bold/italic.
    links: list[str] = []

    def _stash_link(m: "re.Match[str]") -> str:
        links.append(f'<a href="{m.group(2)}" rel="nofollow">{m.group(1)}</a>')
        return f"\x00LINK{len(links) - 1}\x00"

    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', _stash_link, text)

    # **bold** and _italic_. Like CommonMark, an underscore only opens or closes
    # emphasis at a word boundary, so snake_case identifiers (exit_loop,
    # before_tool_callback, __init__) in a technical description stay literal.
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(
        r'(?<![A-Za-z0-9_])_(?![\s_])(.+?)(?<![\s_])_(?![A-Za-z0-9_])',
        r'<em>\1</em>',
        text,
    )

    for i, link_html in enumerate(links):
        text = text.replace(f"\x00LINK{i}\x00", link_html)

    return text


def _build_resources_html(resources: list[tuple[str, str]]) -> str:
    if not resources:
        return ""
    items = "\n".join(
        f' <li><a href="{html.escape(url, quote=True)}" rel="nofollow">'
        f"{html.escape(label, quote=False)}</a></li>"
        for label, url in resources
    )
    return f"\n<p></p>\n<p><strong>Resources:</strong></p>\n<ul>\n{items}\n</ul>"


# ── Input helpers ─────────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    return click.prompt(prompt, default=default, show_default=bool(default))


def _ask_date(prompt: str) -> str:
    while True:
        value = _parse_date(click.prompt(prompt))
        if value:
            return value
        console.print("[red]Invalid date - use YYYY-MM-DD format[/]")


def _ask_url(prompt: str, required: bool = True) -> str:
    while True:
        value = click.prompt(prompt, default="" if not required else None)
        if not value and not required:
            return ""
        parsed = urlparse(value)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return value
        console.print("[red]Invalid URL — must start with http:// or https://[/]")


def _ask_country() -> str:
    return click.prompt("Country", default="")


def _ask_tags() -> list[str]:
    console.print("\nSuggested tags: " + ", ".join(SUGGESTED_TAGS))
    raw = click.prompt("Tags (comma-separated)")
    return [t.strip() for t in raw.split(",") if t.strip()]


def _ask_text_block(label: str) -> str:
    """Collect multiline free text. Two consecutive blank lines = done."""
    click.echo(f"\n{label}")
    click.echo("  Supports Markdown: **bold**, [text](url), * list item, → item")
    click.echo("  Paste your text and press Enter twice on a blank line to finish:\n")
    lines: list[str] = []
    empty_streak = 0
    while True:
        try:
            line = sys.stdin.readline().rstrip("\n")
        except (EOFError, KeyboardInterrupt):
            break
        if line == "":
            empty_streak += 1
            if empty_streak >= 2:
                break
            lines.append("")
        else:
            empty_streak = 0
            lines.append(line)
    return "\n".join(lines).strip()


def _ask_resources() -> list[tuple[str, str]]:
    """Ask for named resources until user submits an empty name."""
    resources: list[tuple[str, str]] = []
    click.echo("\nResources (slides, codelab, GitHub, etc.) — blank name to finish:")
    while True:
        label = click.prompt("  Resource name", default="")
        if not label:
            break
        url = _ask_url("  URL")
        resources.append((label, url))
    return resources


# Advocu rejects drafts with HTTP 400 ("expected maxLength: 2000") once the
# rendered description HTML (tags included) crosses this length.
DESCRIPTION_MAX_LENGTH = 2000

LANGUAGES = ["EN-US", "PT-BR", "ES", "FR", "DE", "JA", "KO", "ZH"]
CONTENT_TYPES = ["Articles", "Videos", "Podcasts", "Other"]
EVENT_FORMATS = ["In-Person", "Virtual", "Hybrid"]


def _format_title(role: str, event: str, talk: str, lang: str) -> str:
    return f"{role} @ {event} - {talk} ({lang})"


# ── Draft specs ───────────────────────────────────────────────────────────────
# A "spec" is the human-level description of a draft: the same answers the
# prompts collect. payload_from_spec() turns it into the API payload, so the
# interactive flow and `advocu submit --file` build drafts the same way.
#
# Notes on API behaviour (confirmed by testing):
#   - submissionDate → set automatically by the API; rejected if sent in POST
#   - city           → requires geocoded autocomplete from the web panel; rejected in POST
#   - eventFormat    → accepted by /activity-drafts/workshop but rejected by /activity-drafts/public-speaking
#   - durationHours  → rejected on /activity-drafts/workshop

class SpecError(ValueError):
    """A draft spec is invalid. `errors` lists every problem found."""

    def __init__(self, errors: str | list[str]):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("\n".join(self.errors))


# kind -> (required keys, optional keys with their defaults)
_SPECS: dict[str, tuple[tuple[str, ...], dict]] = {
    "talk": (
        ("title", "event", "date", "url", "tags"),
        {"role": "Speaker", "attendees": 0, "language": "EN-US", "country": "",
         "description": "", "resources": ()},
    ),
    "workshop": (
        ("title", "event", "date", "url", "tags"),
        {"role": "Workshop Proctor", "attendees": 0, "language": "EN-US", "country": "",
         "event_format": "In-Person", "description": "", "resources": ()},
    ),
    "content": (
        ("title", "date", "url", "tags"),
        {"content_type": "Articles", "language": "EN-US", "readers": 0,
         "description": "", "resources": ()},
    ),
    "story": (
        ("title", "date", "tags"),
        {"url": "", "description": ""},
    ),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _canonical(value, choices: list[str]) -> str | None:
    """Case-insensitive match of `value` against the allowed choices."""
    if isinstance(value, str):
        for choice in choices:
            if choice.lower() == value.strip().lower():
                return choice
    return None


def _parse_date(value) -> str | None:
    """YYYY-MM-DD from a string or a native TOML date, or None if invalid."""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and _DATE_RE.match(value.strip()):
        try:
            date.fromisoformat(value.strip())
        except ValueError:
            return None
        return value.strip()
    return None


def _is_url(value) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _is_count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def payload_from_spec(kind: str, spec: dict) -> dict:
    """Validate a draft spec and build the payload for the Advocu API.

    Raises SpecError listing every problem found, so a file can be fixed in
    one pass instead of one error at a time.
    """
    if kind not in _SPECS:
        raise SpecError(f"Unknown draft type '{kind}'.")
    if not isinstance(spec, dict):
        raise SpecError("The draft must be a set of key = value pairs.")

    required, optional = _SPECS[kind]
    allowed = set(required) | set(optional)
    errors: list[str] = []

    unknown = sorted(set(spec) - allowed)
    if unknown:
        errors.append(
            f"Unknown key(s): {', '.join(unknown)}. Allowed: {', '.join(sorted(allowed))}."
        )
    for key in required:
        if spec.get(key) in (None, "", []):
            errors.append(f"Missing required key: {key}.")

    s = {**optional, **{k: v for k, v in spec.items() if k in allowed}}

    def text(key: str) -> str:
        value = s.get(key, "")
        if not isinstance(value, str):
            errors.append(f"{key} must be text.")
            return ""
        return value.strip()

    title = text("title")
    description = text("description")
    when = _parse_date(s["date"]) if "date" in s else None
    if s.get("date") not in (None, "") and when is None:
        errors.append(f"date must be a real date in YYYY-MM-DD format, got {s['date']!r}.")

    url = text("url") if "url" in s else ""
    if url and not _is_url(url):
        errors.append(f"url must start with http:// or https://, got {url!r}.")

    tags = s.get("tags")
    if tags not in (None, "", []):
        if not isinstance(tags, list) or not all(isinstance(t, str) and t.strip() for t in tags):
            errors.append("tags must be a list of non-empty text values.")
            tags = []
        else:
            tags = [t.strip() for t in tags]

    resources: list[tuple[str, str]] = []
    raw_resources = s.get("resources", ())
    if not isinstance(raw_resources, (list, tuple)):
        errors.append("resources must be a list of {name, url} entries.")
    else:
        for i, item in enumerate(raw_resources, 1):
            name = item.get("name") if isinstance(item, dict) else None
            link = item.get("url") if isinstance(item, dict) else None
            if not (isinstance(name, str) and name.strip() and _is_url(link)):
                errors.append(
                    f"resources #{i} needs a name and a valid http(s) url, got {item!r}."
                )
            else:
                resources.append((name.strip(), link.strip()))

    language = _canonical(s.get("language"), LANGUAGES) if "language" in s else None
    if "language" in s and language is None:
        errors.append(f"language must be one of {', '.join(LANGUAGES)}, got {s['language']!r}.")

    count_key = "readers" if kind == "content" else "attendees"
    count = s.get(count_key, 0)
    if kind in ("talk", "workshop", "content") and not _is_count(count):
        errors.append(f"{count_key} must be a whole number, 0 or more, got {count!r}.")

    content_type = event_format = None
    if kind == "content":
        content_type = _canonical(s.get("content_type"), CONTENT_TYPES)
        if content_type is None:
            errors.append(
                f"content_type must be one of {', '.join(CONTENT_TYPES)}, got {s.get('content_type')!r}."
            )
    if kind == "workshop":
        event_format = _canonical(s.get("event_format"), EVENT_FORMATS)
        if event_format is None:
            errors.append(
                f"event_format must be one of {', '.join(EVENT_FORMATS)}, got {s.get('event_format')!r}."
            )

    country = text("country") if kind in ("talk", "workshop") else ""
    role = (text("role") or optional.get("role", "")) if kind in ("talk", "workshop") else ""
    event = text("event") if kind in ("talk", "workshop") else ""

    if errors:
        raise SpecError(errors)

    if kind in ("talk", "workshop"):
        final_title = _format_title(role, event, title, language)
    elif kind == "content":
        final_title = f"{title} ({language})"
    else:
        final_title = title

    # Stories take no resources list; everything else appends it to the text.
    html_body = _md_to_html(description)
    if kind != "story":
        html_body += _build_resources_html(resources)

    data: dict = {"title": final_title}
    if kind == "content":
        data["contentType"] = content_type
    data["activityDate"] = when
    if url:
        data["activityUrl"] = url
    data["description"] = html_body
    data["tags"] = tags
    if kind != "story":
        data["metrics"] = {count_key: count}
    if kind == "workshop":
        data["eventFormat"] = event_format
    if country:
        data["country"] = country
    data["private"] = False
    return data


def load_spec(path) -> dict:
    """Read a draft spec from a .json or .toml file."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in (".json", ".toml"):
        raise SpecError(f"Unsupported file type '{suffix or path.name}': use a .json or .toml file.")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SpecError(f"Could not read {path}: {e.strerror or e}") from e
    try:
        spec = json.loads(raw) if suffix == ".json" else tomllib.loads(raw)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as e:
        raise SpecError(f"{path.name} is not valid {suffix[1:].upper()}: {e}") from e
    if not isinstance(spec, dict):
        raise SpecError(f"{path.name} must contain key = value pairs at the top level.")
    return spec


def payload_problems(data: dict) -> tuple[list[str], list[str]]:
    """Checks on a finished payload: (errors that block sending, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    size = len(data.get("description", ""))
    if size > DESCRIPTION_MAX_LENGTH:
        errors.append(
            f"description is {size} characters (rendered HTML), and Advocu rejects drafts "
            f"over {DESCRIPTION_MAX_LENGTH} with HTTP 400. Shorten the text."
        )

    unknown = [t for t in data.get("tags", []) if t not in SUGGESTED_TAGS]
    if unknown:
        warnings.append(
            f"Tag(s) not in the built-in list: {', '.join(unknown)}. Advocu rejects tags it does "
            "not know, and the list can be out of date: check the tag dropdown in the web panel."
        )
    return errors, warnings


# ── Preview and confirmation ──────────────────────────────────────────────────

def render_preview(data: dict) -> None:
    lines = []
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"  [cyan]{k}:[/] {escape(', '.join(str(i) for i in v))}")
        elif isinstance(v, dict):
            for sk, sv in v.items():
                lines.append(f"  [cyan]{k}.{sk}:[/] {escape(str(sv)[:100])}")
        else:
            val = str(v)
            lines.append(f"  [cyan]{k}:[/] {escape(val[:120])}{'…' if len(val) > 120 else ''}")
    console.print(Panel("\n".join(lines), title="Payload preview", border_style="blue"))


def print_warnings(messages: list[str]) -> None:
    for message in messages:
        console.print(f"[bold yellow]Warning:[/] {escape(message)}")


def _confirm_payload(data: dict) -> bool:
    render_preview(data)
    errors, warnings = payload_problems(data)
    # Interactively these are advice, not a hard stop: the API has the final say.
    print_warnings(errors + warnings)
    return click.confirm("Submit draft?", default=True)


# ── Interactive builders ──────────────────────────────────────────────────────
# Each one asks the questions, then hands the answers to payload_from_spec().

def _finish(kind: str, spec: dict) -> dict | None:
    try:
        data = payload_from_spec(kind, spec)
    except SpecError as e:
        for problem in e.errors:
            console.print(f"[bold red]Problem:[/] {escape(problem)}")
        return None
    return {"data": data} if _confirm_payload(data) else None


def _ask_language() -> str:
    return click.prompt(
        "Language", default="EN-US", type=click.Choice(LANGUAGES, case_sensitive=False),
    )


def build_talk() -> dict | None:
    click.echo("\n🎤  New talk (public-speaking)\n")

    spec = {
        "role":        _ask("Your role at the event", default="Speaker"),
        "title":       _ask("Talk title"),
        "event":       _ask("Event name"),
        "date":        _ask_date("Activity date (YYYY-MM-DD)"),
        "url":         _ask_url("Event URL"),
        "attendees":   click.prompt("Number of attendees (approx.)", default=0, type=int),
        "language":    _ask_language(),
        "country":     _ask_country(),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text (post, notes, summary):"),
        "resources":   [{"name": n, "url": u} for n, u in _ask_resources()],
    }
    return _finish("talk", spec)


def build_workshop() -> dict | None:
    click.echo("\n🛠️  New workshop\n")

    spec = {
        "role":        _ask("Your role at the event", default="Workshop Proctor"),
        "title":       _ask("Workshop title"),
        "event":       _ask("Event name"),
        "date":        _ask_date("Activity date (YYYY-MM-DD)"),
        "url":         _ask_url("Event URL"),
        "attendees":   click.prompt("Number of attendees", default=0, type=int),
        "language":    _ask_language(),
        "country":     _ask_country(),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text (post, notes, summary):"),
        "resources":   [{"name": n, "url": u} for n, u in _ask_resources()],
    }
    return _finish("workshop", spec)


def build_content() -> dict | None:
    click.echo("\n📝  New content (content-creation)\n")

    spec = {
        "content_type": click.prompt(
            "Content type",
            type=click.Choice(CONTENT_TYPES, case_sensitive=False),
            default="Articles",
        ),
        "title":       _ask("Title"),
        "date":        _ask_date("Publication date (YYYY-MM-DD)"),
        "url":         _ask_url("Content URL"),
        "language":    _ask_language(),
        "readers":     click.prompt("Views / readers (approx.)", default=0, type=int),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text:"),
        "resources":   [{"name": n, "url": u} for n, u in _ask_resources()],
    }
    return _finish("content", spec)


def build_story() -> dict | None:
    click.echo("\n📸  New story\n")

    spec = {
        "title":       _ask("Title / caption"),
        "date":        _ask_date("Activity date (YYYY-MM-DD)"),
        "url":         _ask_url("Story URL (optional)", required=False),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Description:"),
    }
    return _finish("story", spec)
