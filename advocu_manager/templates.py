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

# Tags the Advocu API accepts. Anything outside this list is rejected with a 400
# ("is not a valid enum value"). Advocu adds, renames and retires tags without
# notice (the Cloud tags were reorganised between September and November 2026),
# so this list is checked against the live API rather than copied from the web
# panel: run `python tools/check_api.py` to see what has drifted.
# Last verified against the API on 2026-11-07 (67 tags).
SUGGESTED_TAGS = [
    # AI
    "AI",
    "AI - Agent Development Kit (ADK)",
    "AI - AI Studio",
    "AI - Antigravity",
    "AI - Colab",
    "AI - Gemini",
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
    "Android - XR",
    # Cloud
    "Cloud - Gemini Platform",
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
    "Build with AI",
    "DevFest",
    "Earth Engine",
    "Golang",
    "Google Cloud",
    "Google I/O Extended",
    "Google Maps Platform",
    "Google Workspace",
    "Open Source",
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


# ── Limits and allowed values ─────────────────────────────────────────────────
# Everything here was checked against the live API (2026-11-07) with requests
# that the API always rejects, so nothing was created. `python tools/check_api.py`
# repeats the check and reports what has drifted.

# Advocu rejects drafts with HTTP 400 ("expected maxLength: 2000") once the
# rendered description HTML (tags included) crosses this length.
DESCRIPTION_MAX_LENGTH = 2000
ADDITIONAL_INFO_MAX_LENGTH = 2000
PRODUCT_DESCRIPTION_MAX_LENGTH = 500  # rendered HTML, product-feedback-given only
TITLE_MIN_LENGTH = 3
TITLE_MAX_LENGTH = 200

LANGUAGES = ["EN-US", "PT-BR", "ES", "FR", "DE", "JA", "KO", "ZH"]
CONTENT_TYPES = ["Articles", "Videos", "Podcasts", "Books", "Newsletters", "Demos"]
EVENT_FORMATS = ["In-Person", "Virtual", "Hybrid"]
INTERACTION_FORMATS = [
    "Survey",
    "Video feedback",
    "In-person feedback sessions",
    "Online feedback sessions",
    "Feedback summits",
    "User study / focus group",
    "Feedback submissions",
    "Other",
]
INTERACTION_TYPES = [
    "Product feedback (research studies, roadmap input, Customer Advisory Boards, EAP)",
    "File bugs / help out with finding bugs",
    "GitHub",
    "Stack Overflow",
    "Industry",
    "Other interactions with Google Product Teams",
]
FEEDBACK_TYPES = ["Early access program", "Product feedback session"]
SIGNIFICANCE_TYPES = [
    "Diversity & Inclusion",
    "Helping Business",
    "Social Impact",
    "Feedback to Google",
    "Community Leading",
    "Technology / Open source",
]


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
#   - imageUrl       → rejected; the cover image is uploaded in the web panel
#   - durationHours  → rejected on every endpoint
#   - metrics        → whole numbers, 1 or more (0 is rejected): leave a metric out if unknown
#   - an empty draft is accepted (HTTP 201), so never probe an endpoint with {}

class SpecError(ValueError):
    """A draft spec is invalid. `errors` lists every problem found."""

    def __init__(self, errors: str | list[str]):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("\n".join(self.errors))


_TEXTS = {"description": "", "additional_info": ""}

# kind -> (required keys, optional keys with their defaults; None = leave it out)
_SPECS: dict[str, tuple[tuple[str, ...], dict]] = {
    "talk": (
        ("title", "event", "date", "url", "tags"),
        {"role": "Speaker", "attendees": None, "in_person_attendees": None,
         "language": "EN-US", "country": "", "event_format": None,
         "resources": (), **_TEXTS},
    ),
    "workshop": (
        ("title", "event", "date", "url", "tags"),
        {"role": "Workshop Proctor", "attendees": None, "in_person_attendees": None,
         "language": "EN-US", "country": "", "event_format": "In-Person",
         "resources": (), **_TEXTS},
    ),
    "content": (
        ("title", "date", "url", "tags"),
        {"content_type": "Articles", "language": "EN-US", "readers": None,
         "resources": (), **_TEXTS},
    ),
    # Stories have no date in the API (activityDate is rejected). Their text is
    # Advocu's "Why is this significant?" field, whyIsSignificant, so the spec's
    # `description` goes there; the metric is `impact` (people reached).
    "story": (
        ("title", "tags"),
        {"url": "", "significance_type": None, "impact": None, **_TEXTS},
    ),
    "interaction": (
        ("title", "date", "tags", "interaction_type", "format"),
        {"event": "", "language": "EN-US", "minutes": None, "additional_links": "",
         "resources": (), **_TEXTS},
    ),
    "feedback": (
        ("title", "date", "tags", "product_description"),
        {"content_type": "Product feedback session", "language": "EN-US", "minutes": None,
         "resources": (), **_TEXTS},
    ),
    "mentoring": (
        ("title", "date", "tags"),
        {"language": "EN-US", "url": "", "country": "", "event_format": None,
         "attendees": None, "in_person_attendees": None, "resources": (), **_TEXTS},
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

    # A key set to null (JSON) counts as not given.
    s = {**optional, **{k: v for k, v in spec.items() if k in allowed and v is not None}}

    def text(key: str) -> str:
        value = s.get(key, "")
        if not isinstance(value, str):
            errors.append(f"{key} must be text.")
            return ""
        return value.strip()

    def count(key: str, minimum: int) -> int | None:
        value = s.get(key)
        if value is None:
            return None
        if not (isinstance(value, int) and not isinstance(value, bool) and value >= minimum):
            errors.append(
                f"{key} must be a whole number, {minimum} or more (leave it out if unknown), got {value!r}."
            )
            return None
        return value

    def choice(key: str, choices: list[str]) -> str | None:
        value = s.get(key)
        if value is None or (value == "" and key not in required):
            return None
        match = _canonical(value, choices)
        if match is None and key in s:
            errors.append(f"{key} must be one of {', '.join(choices)}, got {value!r}.")
        return match

    title = text("title")
    description = text("description")
    additional_info = text("additional_info")

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

    language = (choice("language", LANGUAGES) or "EN-US") if "language" in s else None
    event_format = choice("event_format", EVENT_FORMATS) if "event_format" in s else None
    content_type = None
    if kind == "content":
        content_type = choice("content_type", CONTENT_TYPES)
    elif kind == "feedback":
        content_type = choice("content_type", FEEDBACK_TYPES)

    interaction_type = choice("interaction_type", INTERACTION_TYPES) if kind == "interaction" else None
    interaction_format = choice("format", INTERACTION_FORMATS) if kind == "interaction" else None
    significance = choice("significance_type", SIGNIFICANCE_TYPES) if kind == "story" else None

    attendees = count("attendees", 1) if "attendees" in s else None
    in_person = count("in_person_attendees", 0) if "in_person_attendees" in s else None
    readers = count("readers", 1) if "readers" in s else None
    minutes = count("minutes", 1) if "minutes" in s else None
    impact = count("impact", 1) if "impact" in s else None

    role = (text("role") or optional.get("role", "")) if "role" in s else ""
    event = text("event") if "event" in s else ""
    country = text("country") if "country" in s else ""
    additional_links = text("additional_links") if "additional_links" in s else ""
    product_description = text("product_description") if kind == "feedback" else ""

    if errors:
        raise SpecError(errors)

    # Titles carry the language the material was delivered in.
    if kind in ("talk", "workshop"):
        final_title = _format_title(role, event, title, language)
    elif kind == "interaction":
        base = f"{title} @ {event}" if event else title
        final_title = f"{base} ({language})"
    elif kind == "story":
        final_title = title
    else:
        final_title = f"{title} ({language})"

    # Stories take no resources list; everything else appends it to the text.
    html_body = _md_to_html(description)
    if kind != "story":
        html_body += _build_resources_html(resources)

    data: dict = {"title": final_title}
    if kind in ("content", "feedback"):
        data["contentType"] = content_type
    if kind == "interaction":
        data["interactionType"] = interaction_type
        data["format"] = interaction_format
    if kind == "story" and significance:
        data["significanceType"] = significance
    if kind != "story":
        data["activityDate"] = when
    if url and kind in ("talk", "workshop", "content", "story", "mentoring"):
        data["activityUrl"] = url
    data["whyIsSignificant" if kind == "story" else "description"] = html_body
    if kind == "feedback":
        data["productDescription"] = _md_to_html(product_description)
    data["tags"] = tags

    metrics = {}
    if kind == "content" and readers:
        metrics["readers"] = readers
    if kind in ("talk", "workshop", "mentoring") and attendees:
        metrics["attendees"] = attendees
    if kind in ("interaction", "feedback") and minutes:
        metrics["timeSpent"] = minutes
    if kind == "story" and impact:
        metrics["impact"] = impact
    if metrics:
        data["metrics"] = metrics

    if in_person is not None and kind in ("talk", "workshop", "mentoring"):
        data["inPersonAttendees"] = in_person
    if event_format and kind in ("talk", "workshop", "mentoring"):
        data["eventFormat"] = event_format
    if country and kind in ("talk", "workshop", "mentoring"):
        data["country"] = country
    if additional_links:
        data["additionalLinks"] = additional_links
    if additional_info:
        data["additionalInfo"] = additional_info
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

    def too_long(key: str, limit: int, label: str) -> None:
        size = len(data.get(key) or "")
        if size > limit:
            errors.append(
                f"{label} is {size} characters, and Advocu rejects more than {limit} with HTTP 400. Shorten the text."
            )

    title_size = len(data.get("title", ""))
    if not TITLE_MIN_LENGTH <= title_size <= TITLE_MAX_LENGTH:
        errors.append(
            f"title is {title_size} characters, and Advocu accepts {TITLE_MIN_LENGTH} to {TITLE_MAX_LENGTH}. "
            "The final title includes the role, event and language."
        )
    too_long("description", DESCRIPTION_MAX_LENGTH, "description (rendered HTML)")
    too_long("whyIsSignificant", DESCRIPTION_MAX_LENGTH, "description (rendered HTML)")
    too_long("additionalInfo", ADDITIONAL_INFO_MAX_LENGTH, "additional_info")
    too_long("productDescription", PRODUCT_DESCRIPTION_MAX_LENGTH, "product_description (rendered HTML)")

    unknown = [t for t in data.get("tags", []) if t not in SUGGESTED_TAGS]
    if unknown:
        warnings.append(
            f"Tag(s) not in the built-in list: {', '.join(unknown)}. Advocu rejects tags it does "
            "not know, and the list can be out of date: check the tag dropdown in the web panel."
        )

    fmt = data.get("eventFormat")
    if fmt in ("In-Person", "Hybrid") and not data.get("country"):
        warnings.append(f"{fmt} events usually need a country; the city is set later in the web panel.")
    if fmt == "Hybrid" and "inPersonAttendees" not in data:
        warnings.append("Hybrid events usually need in_person_attendees (how many were in the room).")
    total = (data.get("metrics") or {}).get("attendees")
    in_room = data.get("inPersonAttendees")
    if total and in_room and in_room > total:
        warnings.append(f"in_person_attendees ({in_room}) is larger than attendees ({total}).")
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


def _ask_choice(label: str, choices: list[str], default: str | None = None) -> str:
    return click.prompt(label, default=default, type=click.Choice(choices, case_sensitive=False))


def _ask_count(label: str) -> int | None:
    """A number, or nothing: the API refuses 0, so 0 means 'leave it out'."""
    return click.prompt(f"{label} (0 to skip)", default=0, type=int) or None


def _resources() -> list[dict]:
    return [{"name": n, "url": u} for n, u in _ask_resources()]


def _event_questions() -> dict:
    """Format, and how many people were in the room for a hybrid event."""
    event_format = _ask_choice("Event format", EVENT_FORMATS, default="In-Person")
    spec = {"event_format": event_format}
    if event_format == "Hybrid":
        spec["in_person_attendees"] = _ask_count("In-person attendees")
    return spec


def build_talk() -> dict | None:
    click.echo("\n🎤  New talk (public-speaking)\n")

    spec = {
        "role":        _ask("Your role at the event", default="Speaker"),
        "title":       _ask("Talk title"),
        "event":       _ask("Event name"),
        "date":        _ask_date("Activity date (YYYY-MM-DD)"),
        "url":         _ask_url("Event URL"),
        "attendees":   _ask_count("Number of attendees (approx.)"),
        **_event_questions(),
        "language":    _ask_language(),
        "country":     _ask_country(),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text (post, notes, summary):"),
        "resources":   _resources(),
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
        "attendees":   _ask_count("Number of attendees"),
        **_event_questions(),
        "language":    _ask_language(),
        "country":     _ask_country(),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text (post, notes, summary):"),
        "resources":   _resources(),
    }
    return _finish("workshop", spec)


def build_content() -> dict | None:
    click.echo("\n📝  New content (content-creation)\n")

    spec = {
        "content_type": _ask_choice("Content type", CONTENT_TYPES, default="Articles"),
        "title":       _ask("Title"),
        "date":        _ask_date("Publication date (YYYY-MM-DD)"),
        "url":         _ask_url("Content URL"),
        "language":    _ask_language(),
        "readers":     _ask_count("Views / readers (approx.)"),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text:"),
        "resources":   _resources(),
    }
    return _finish("content", spec)


def build_story() -> dict | None:
    click.echo("\n📸  New story\n")

    spec = {
        "title":       _ask("Title / caption"),
        "url":         _ask_url("Story URL (optional)", required=False),
        "significance_type": _ask_choice("Significance", SIGNIFICANCE_TYPES),
        "impact":      _ask_count("People reached or impacted"),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Why is this significant?"),
    }
    return _finish("story", spec)


def build_interaction() -> dict | None:
    click.echo("\n🤝  New interaction with Googlers\n")

    spec = {
        "title":       _ask("Title (what was the session?)"),
        "event":       _ask("Event or program (optional)", default=""),
        "date":        _ask_date("Activity date (YYYY-MM-DD)"),
        "interaction_type": _ask_choice("Interaction type", INTERACTION_TYPES),
        "format":      _ask_choice("Format", INTERACTION_FORMATS),
        "minutes":     _ask_count("Time spent, in minutes"),
        "language":    _ask_language(),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text:"),
        "additional_links": _ask("Additional links (optional)", default=""),
        "resources":   _resources(),
    }
    return _finish("interaction", spec)


def build_feedback() -> dict | None:
    click.echo("\n🧪  New product feedback\n")

    spec = {
        "title":       _ask("Title (what was the session?)"),
        "date":        _ask_date("Activity date (YYYY-MM-DD)"),
        "content_type": _ask_choice("Type", FEEDBACK_TYPES, default="Product feedback session"),
        "product_description": _ask("Which product was the feedback about? (max 500 characters)"),
        "minutes":     _ask_count("Time spent, in minutes"),
        "language":    _ask_language(),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text:"),
        "resources":   _resources(),
    }
    return _finish("feedback", spec)


def build_mentoring() -> dict | None:
    click.echo("\n🧭  New mentoring\n")

    spec = {
        "title":       _ask("Title"),
        "date":        _ask_date("Activity date (YYYY-MM-DD)"),
        "url":         _ask_url("Related URL (optional)", required=False),
        "attendees":   _ask_count("People mentored, in total"),
        **_event_questions(),
        "language":    _ask_language(),
        "country":     _ask_country(),
        "tags":        _ask_tags(),
        "description": _ask_text_block("Descriptive text:"),
        "resources":   _resources(),
    }
    return _finish("mentoring", spec)
