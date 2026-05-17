"""Interactive prompts that build draft payloads for each activity type."""

from __future__ import annotations

import re
import sys
from datetime import date
from urllib.parse import urlparse

import click
from rich.console import Console
from rich.panel import Panel

console = Console()

# Reference list shown to the user — not enforced, free-form input is accepted
SUGGESTED_TAGS = [
    # AI / ML — confirmed active in Advocu API
    "AI",
    "AI - Colab",
    "AI - Gemini",
    "AI - Generative AI",
    "AI - Agents",
    "AI - Agent Development Kit (ADK)",
    "AI - TensorFlow",
    "Build with AI",
    "Machine Learning",
    "Deep Learning",
    "Data Analysis",
    # ML Focus Areas
    "ML Focus Area - Responsible ML/AI",
    # ML Products
    "ML Products - JAX/Flax",
    "ML Products - Keras",
    "ML Products - TensorFlow Core",
    # GDE tracks
    "Android",
    "Flutter",
    "Firebase",
    "Angular",
    "Web",
    "Go",
    "Kotlin",
    "Cloud",
    "Google Cloud",
    "Google Maps Platform",
    "Payments",
    # Other common GDE activity tags
    "Python",
    "Data Science",
    "Security",
    "Open Source",
    "DevOps",
    "Accessibility",
    "Community",
    "Education",
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
    # [text](url) → <a>
    text = re.sub(
        r'\[([^\]]+)\]\((https?://[^\)]+)\)',
        r'<a href="\2" rel="nofollow">\1</a>',
        text,
    )
    # **bold** and _italic_
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    return text


def _build_resources_html(resources: list[tuple[str, str]]) -> str:
    if not resources:
        return ""
    items = "\n".join(
        f' <li><a href="{url}" rel="nofollow">{label}</a></li>'
        for label, url in resources
    )
    return f"\n<p></p>\n<p><strong>Resources:</strong></p>\n<ul>\n{items}\n</ul>"


# ── Input helpers ─────────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    return click.prompt(prompt, default=default, show_default=bool(default))


def _ask_date(prompt: str) -> str:
    while True:
        value = click.prompt(prompt)
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            console.print("[red]Invalid date — use YYYY-MM-DD format[/]")


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


def _confirm_payload(data: dict) -> bool:
    lines = []
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"  [cyan]{k}:[/] {', '.join(str(i) for i in v)}")
        elif isinstance(v, dict):
            for sk, sv in v.items():
                lines.append(f"  [cyan]{k}.{sk}:[/] {str(sv)[:100]}")
        else:
            val = str(v)
            lines.append(f"  [cyan]{k}:[/] {val[:120]}{'…' if len(val) > 120 else ''}")
    console.print(Panel("\n".join(lines), title="Payload preview", border_style="blue"))
    return click.confirm("Submit draft?", default=True)


def _format_title(role: str, event: str, talk: str, lang: str) -> str:
    return f"{role} @ {event} - {talk} ({lang})"


# ── Template builders ─────────────────────────────────────────────────────────
# Notes on API behaviour (confirmed by testing):
#   - submissionDate → set automatically by the API; rejected if sent in POST
#   - city           → requires geocoded autocomplete from the web panel; rejected in POST
#   - eventFormat    → accepted by /activity-drafts/workshop but rejected by /activity-drafts/public-speaking


def build_talk() -> dict | None:
    click.echo("\n🎤  New talk (public-speaking)\n")

    role          = _ask("Your role at the event", default="Speaker")
    talk_title    = _ask("Talk title")
    event_name    = _ask("Event name")
    activity_date = _ask_date("Activity date (YYYY-MM-DD)")
    event_url     = _ask_url("Event URL")
    attendees     = click.prompt("Number of attendees (approx.)", default=0, type=int)
    language      = click.prompt(
        "Language", default="EN-US",
        type=click.Choice(["EN-US", "PT-BR", "ES", "FR", "DE", "JA", "KO", "ZH"], case_sensitive=False),
    )
    country       = _ask_country()
    tags          = _ask_tags()
    body_text     = _ask_text_block("Descriptive text (post, notes, summary):")
    resources     = _ask_resources()

    data: dict = {
        "title": _format_title(role, event_name, talk_title, language),
        "activityDate": activity_date,
        "activityUrl": event_url,
        "description": _md_to_html(body_text) + _build_resources_html(resources),
        "tags": tags,
        "metrics": {"attendees": attendees},
        "country": country,
        "private": False,
    }
    if not country:
        data.pop("country")

    return {"data": data} if _confirm_payload(data) else None


def build_workshop() -> dict | None:
    click.echo("\n🛠️  New workshop\n")

    role           = _ask("Your role at the event", default="Workshop Proctor")
    workshop_title = _ask("Workshop title")
    event_name     = _ask("Event name")
    activity_date  = _ask_date("Activity date (YYYY-MM-DD)")
    event_url      = _ask_url("Event URL")
    attendees      = click.prompt("Number of attendees", default=0, type=int)
    duration       = click.prompt("Duration in hours (0 = skip)", default=0, type=int)
    language       = click.prompt(
        "Language", default="EN-US",
        type=click.Choice(["EN-US", "PT-BR", "ES", "FR", "DE", "JA", "KO", "ZH"], case_sensitive=False),
    )
    country        = _ask_country()
    tags           = _ask_tags()
    body_text      = _ask_text_block("Descriptive text (post, notes, summary):")
    resources      = _ask_resources()

    data: dict = {
        "title": _format_title(role, event_name, workshop_title, language),
        "activityDate": activity_date,
        "activityUrl": event_url,
        "description": _md_to_html(body_text) + _build_resources_html(resources),
        "tags": tags,
        "metrics": {"attendees": attendees},
        "eventFormat": "In-Person",
        "country": country,
        "private": False,
    }
    if not country:
        data.pop("country")
    if duration:
        data["durationHours"] = duration

    return {"data": data} if _confirm_payload(data) else None


def build_content() -> dict | None:
    click.echo("\n📝  New content (content-creation)\n")

    content_type = click.prompt(
        "Content type",
        type=click.Choice(["Articles", "Videos", "Podcasts", "Other"], case_sensitive=False),
        default="Articles",
    )
    title     = _ask("Title")
    pub_date  = _ask_date("Publication date (YYYY-MM-DD)")
    url       = _ask_url("Content URL")
    language  = click.prompt(
        "Language", default="EN-US",
        type=click.Choice(["EN-US", "PT-BR", "ES", "FR", "DE", "JA", "KO", "ZH"], case_sensitive=False),
    )
    readers   = click.prompt("Views / readers (approx.)", default=0, type=int)
    tags      = _ask_tags()
    body_text = _ask_text_block("Descriptive text:")
    resources = _ask_resources()

    data: dict = {
        "title": f"{title} ({language})",
        "contentType": content_type,
        "activityDate": pub_date,
        "activityUrl": url,
        "description": _md_to_html(body_text) + _build_resources_html(resources),
        "tags": tags,
        "metrics": {"readers": readers},
        "private": False,
    }

    return {"data": data} if _confirm_payload(data) else None


def build_story() -> dict | None:
    click.echo("\n📸  New story\n")

    title         = _ask("Title / caption")
    activity_date = _ask_date("Activity date (YYYY-MM-DD)")
    url           = _ask_url("Story URL (optional)", required=False)
    tags          = _ask_tags()
    body_text     = _ask_text_block("Description:")

    data: dict = {
        "title": title,
        "activityDate": activity_date,
        "description": _md_to_html(body_text),
        "tags": tags,
        "private": False,
    }
    if url:
        data["activityUrl"] = url

    return {"data": data} if _confirm_payload(data) else None
