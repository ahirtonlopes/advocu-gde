from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date

import click
from rich.console import Console
from rich.table import Table
from rich import box

from .api import AdvocuClient
from .templates import build_talk, build_workshop, build_content, build_story

console = Console()


def get_client(token: str | None) -> AdvocuClient:
    try:
        return AdvocuClient(token)
    except ValueError as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


# ── Root group ───────────────────────────────────────────────────────────────

@click.group()
@click.option(
    "--token", "-t",
    envvar="ADVOCU_TOKEN",
    default=None,
    help="API token (or env ADVOCU_TOKEN).",
)
@click.pass_context
def cli(ctx, token):
    """advocu-gde — Manage your Advocu activities via the Personal API."""
    ctx.ensure_object(dict)
    ctx.obj["token"] = token


# ── list ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--json-out", is_flag=True, help="Export raw JSON.")
@click.pass_context
def list(ctx, json_out):
    """List all activities (automatic pagination)."""
    client = get_client(ctx.obj["token"])
    with console.status("Fetching activities…"):
        activities = client.list_all_activities()

    if json_out:
        click.echo(json.dumps(activities, indent=2, ensure_ascii=False))
        return

    _render_table(activities)
    console.print(f"\n[bold]{len(activities)}[/] activity(ies) found.")


# ── recent ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("n", default=10, type=int)
@click.option("--json-out", is_flag=True, help="Export raw JSON.")
@click.pass_context
def recent(ctx, n, json_out):
    """Show the N most recent activities. [default: 10]"""
    client = get_client(ctx.obj["token"])
    with console.status("Fetching activities…"):
        activities = client.list_all_activities()

    # Sort by activityDate (primary) and submissionDate (tiebreak)
    activities.sort(
        key=lambda a: (
            a.get("data", {}).get("activityDate") or "",
            a.get("submissionDate") or "",
        ),
        reverse=True,
    )
    top = activities[:n]

    if json_out:
        click.echo(json.dumps(top, indent=2, ensure_ascii=False))
        return

    _render_table(top)
    console.print(f"\nShowing [bold]{len(top)}[/] of [bold]{len(activities)}[/] activity(ies).")


# ── update ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("activity_id")
@click.option("--field", "-f", multiple=True, metavar="KEY=VALUE",
              help="Field to update, e.g. -f title='New title'")
@click.option("--json-payload", "-j", default=None,
              help='Fields as JSON, e.g. \'{"title":"New title"}\'')
@click.pass_context
def update(ctx, activity_id, field, json_payload):
    """Update fields of an existing activity via PATCH."""
    if not field and not json_payload:
        console.print("[bold red]Error:[/] provide --field KEY=VALUE or --json-payload '{…}'")
        sys.exit(1)

    fields: dict = {}
    if json_payload:
        try:
            fields = json.loads(json_payload)
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON:[/] {e}")
            sys.exit(1)
    for f in field:
        if "=" not in f:
            console.print(f"[bold red]Invalid format:[/] '{f}' — use KEY=VALUE")
            sys.exit(1)
        k, v = f.split("=", 1)
        fields[k.strip()] = v.strip()

    client = get_client(ctx.obj["token"])
    with console.status(f"Updating {activity_id}…"):
        result = client.update_activity(activity_id, fields)

    console.print("[green]✓ Activity updated![/]")
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


# ── submit ────────────────────────────────────────────────────────────────────

@cli.group()
def submit():
    """Submit an activity draft."""


def _post_result(result: dict):
    draft_id = result.get("id") or result.get("activityId") or "?"
    console.print(f"\n[green]✓ Draft created![/] ID: [bold]{draft_id}[/]")
    console.print("\n[yellow]Next steps in the Advocu panel:[/]")
    console.print("  1. Select your [bold]city[/] via autocomplete")
    console.print("  2. Upload a [bold]cover image[/]")
    console.print("  3. [bold]Publish[/]\n")


@submit.command("talk")
@click.pass_context
def submit_talk(ctx):
    """Draft a talk (public-speaking)."""
    payload = build_talk()
    if payload is None:
        console.print("Cancelled.")
        return
    client = get_client(ctx.obj["token"])
    with console.status("Submitting…"):
        result = client.create_talk_draft(payload["data"])
    _post_result(result)


@submit.command("workshop")
@click.pass_context
def submit_workshop(ctx):
    """Draft a workshop."""
    payload = build_workshop()
    if payload is None:
        console.print("Cancelled.")
        return
    client = get_client(ctx.obj["token"])
    with console.status("Submitting…"):
        result = client.create_workshop_draft(payload["data"])
    _post_result(result)


@submit.command("content")
@click.pass_context
def submit_content(ctx):
    """Draft a content activity (article, video, podcast…)."""
    payload = build_content()
    if payload is None:
        console.print("Cancelled.")
        return
    client = get_client(ctx.obj["token"])
    with console.status("Submitting…"):
        result = client.create_content_draft(payload["data"])
    _post_result(result)


@submit.command("story")
@click.pass_context
def submit_story(ctx):
    """Draft a story."""
    payload = build_story()
    if payload is None:
        console.print("Cancelled.")
        return
    client = get_client(ctx.obj["token"])
    with console.status("Submitting…"):
        result = client.create_story_draft(payload["data"])
    _post_result(result)


# ── stats ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--year", "-y", default=None, type=int,
              help="Filter by year (e.g. --year 2025). Omit for all-time.")
@click.pass_context
def stats(ctx, year):
    """Show a summary of your activity contributions."""
    client = get_client(ctx.obj["token"])
    with console.status("Fetching activities…"):
        activities = client.list_all_activities()

    if year:
        activities = [
            a for a in activities
            if (a.get("data", {}).get("activityDate") or "").startswith(str(year))
        ]

    if not activities:
        label = str(year) if year else "all time"
        console.print(f"[yellow]No activities found for {label}.[/]")
        return

    # ── Aggregate ──────────────────────────────────────────────────────────────
    by_type: Counter = Counter()
    by_year: Counter = Counter()
    content_subtypes: Counter = Counter()
    total_attendees = 0
    total_readers = 0

    for a in activities:
        atype = a.get("type", "unknown")
        inner = a.get("data", {})
        by_type[atype] += 1

        act_date = inner.get("activityDate", "")
        if act_date:
            by_year[act_date[:4]] += 1

        metrics = inner.get("metrics", {}) or {}
        total_attendees += metrics.get("attendees", 0) or 0
        total_readers += metrics.get("readers", 0) or 0

        if atype == "content-creation":
            subtype = inner.get("contentType", "Other")
            content_subtypes[subtype] += 1

    label = str(year) if year else "All time"

    # ── Overview ───────────────────────────────────────────────────────────────
    console.print(f"\n[bold cyan]── {label} overview ──────────────────────────────[/]")
    console.print(f"  [bold]{len(activities)}[/] total activities")
    if total_attendees:
        console.print(f"  [bold]{total_attendees:,}[/] total attendees (talks + workshops)")
    if total_readers:
        console.print(f"  [bold]{total_readers:,}[/] total views / readers (content)")

    # ── By type ────────────────────────────────────────────────────────────────
    console.print(f"\n[bold cyan]── By type ──────────────────────────────────────[/]")
    type_labels = {
        "public-speaking":  "Talks / Panels",
        "workshop":         "Workshops",
        "content-creation": "Content",
        "stories":          "Stories",
        "github-repository":"GitHub Repos",
    }
    for atype, count in by_type.most_common():
        label_str = type_labels.get(atype, atype)
        bar = "█" * count
        console.print(f"  {label_str:<18} [bold]{count:>3}[/]  [dim]{bar}[/]")

    if content_subtypes:
        console.print(f"\n[bold cyan]── Content breakdown ────────────────────────────[/]")
        for subtype, count in content_subtypes.most_common():
            bar = "█" * count
            console.print(f"  {subtype:<18} [bold]{count:>3}[/]  [dim]{bar}[/]")

    # ── By year (only shown in all-time mode) ──────────────────────────────────
    if not year and len(by_year) > 1:
        console.print(f"\n[bold cyan]── By year ──────────────────────────────────────[/]")
        for yr in sorted(by_year):
            count = by_year[yr]
            bar = "█" * min(count, 40)
            console.print(f"  {yr}  [bold]{count:>3}[/]  [dim]{bar}[/]")

    console.print()


# ── fix-date ──────────────────────────────────────────────────────────────────

@cli.command("fix-date")
@click.argument("activity_id")
@click.argument("new_date")
@click.option("--field", default="activityDate",
              type=click.Choice(["activityDate", "submissionDate"]),
              show_default=True,
              help="Which date field to fix.")
@click.pass_context
def fix_date(ctx, activity_id, new_date, field):
    """Shortcut to fix a date field on an existing activity.

    \b
    Examples:
      advocu fix-date <activityId> 2024-03-15
      advocu fix-date <activityId> 2024-03-15 --field submissionDate
    """
    try:
        date.fromisoformat(new_date)
    except ValueError:
        console.print("[bold red]Invalid date:[/] use YYYY-MM-DD format")
        sys.exit(1)

    client = get_client(ctx.obj["token"])
    with console.status(f"Fixing {field} → {new_date}…"):
        result = client.update_activity(activity_id, {field: new_date})

    console.print(f"[green]✓ {field} updated to {new_date}![/]")
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


# ── helpers ───────────────────────────────────────────────────────────────────

def _render_table(activities: list[dict]):
    table = Table(box=box.ROUNDED, show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold", max_width=45)
    table.add_column("Event Date", style="green", no_wrap=True)
    table.add_column("Sub. Date", style="green", no_wrap=True)
    table.add_column("Status", style="yellow")

    for a in activities:
        inner = a.get("data") or {}
        aid = str(a.get("activityId") or a.get("id") or "—")
        atype = a.get("type") or "—"
        title = inner.get("title") or a.get("title") or "—"
        activity_date = inner.get("activityDate") or "—"
        sub_date = (a.get("submissionDate") or "—")[:10]
        status = a.get("status") or a.get("state") or "—"
        table.add_row(aid, atype, title, activity_date, sub_date, status)

    console.print(table)
