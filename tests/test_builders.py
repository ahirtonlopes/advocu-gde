"""Integration tests for the interactive payload builders in templates.py.

Every prompt function is monkeypatched so these run without touching stdin.
"""

import advocu_manager.templates as templates


def _patch_common_prompts(monkeypatch, *, attendees=40, country="Brazil"):
    monkeypatch.setattr(templates, "_ask", lambda prompt, default="": default or "answer")
    monkeypatch.setattr(templates, "_ask_date", lambda prompt: "2026-07-12")
    monkeypatch.setattr(templates, "_ask_url", lambda prompt, required=True: "https://example.com")
    monkeypatch.setattr(templates, "_ask_country", lambda: country)
    monkeypatch.setattr(templates, "_ask_tags", lambda: ["AI"])
    monkeypatch.setattr(templates, "_ask_text_block", lambda label: "Body text.")
    monkeypatch.setattr(templates, "_ask_resources", lambda: [])
    monkeypatch.setattr(
        templates.click,
        "prompt",
        lambda prompt, default=None, type=None, **kw: default if default is not None else attendees,
    )


def test_build_workshop_never_sends_duration_hours(monkeypatch):
    # Regression: the API rejects durationHours as an extraneous key on
    # /activity-drafts/workshop (discovered via a live 400 response).
    _patch_common_prompts(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        templates, "_confirm_payload", lambda data: captured.update(data) or True
    )

    payload = templates.build_workshop()

    assert payload is not None
    assert "durationHours" not in captured
    assert captured["eventFormat"] == "In-Person"


def test_build_workshop_drops_empty_country(monkeypatch):
    _patch_common_prompts(monkeypatch, country="")
    captured = {}
    monkeypatch.setattr(
        templates, "_confirm_payload", lambda data: captured.update(data) or True
    )

    templates.build_workshop()

    assert "country" not in captured


def test_build_workshop_returns_none_when_not_confirmed(monkeypatch):
    _patch_common_prompts(monkeypatch)
    monkeypatch.setattr(templates, "_confirm_payload", lambda data: False)

    assert templates.build_workshop() is None


def test_build_talk_does_not_set_event_format(monkeypatch):
    # eventFormat is rejected by /activity-drafts/public-speaking.
    _patch_common_prompts(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        templates, "_confirm_payload", lambda data: captured.update(data) or True
    )

    templates.build_talk()

    assert "eventFormat" not in captured
