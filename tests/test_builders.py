"""Integration tests for the interactive payload builders in templates.py.

Every prompt function is monkeypatched so these run without touching stdin.
"""

import pytest

import advocu_manager.templates as templates

CHOICES = {
    "Interaction type": templates.INTERACTION_TYPES[0],
    "Format": templates.INTERACTION_FORMATS[3],
    "Significance": templates.SIGNIFICANCE_TYPES[4],
}


def _patch_common_prompts(monkeypatch, *, counts=None, country="Brazil", event_format=None):
    """`counts` maps the start of a prompt to the number typed; the rest keep the default."""
    counts = counts or {}

    def prompt(label, default=None, type=None, **kw):
        if label in CHOICES:
            return CHOICES[label]
        if label == "Event format" and event_format:
            return event_format
        for start, number in counts.items():
            if label.startswith(start):
                return number
        return default

    monkeypatch.setattr(templates, "_ask", lambda label, default="": default or "answer")
    monkeypatch.setattr(templates, "_ask_date", lambda label: "2026-07-12")
    monkeypatch.setattr(templates, "_ask_url", lambda label, required=True: "https://example.com")
    monkeypatch.setattr(templates, "_ask_country", lambda: country)
    monkeypatch.setattr(templates, "_ask_tags", lambda: ["AI"])
    monkeypatch.setattr(templates, "_ask_text_block", lambda label: "Body text.")
    monkeypatch.setattr(templates, "_ask_resources", lambda: [])
    monkeypatch.setattr(templates.click, "prompt", prompt)


def _capture(monkeypatch):
    captured = {}
    monkeypatch.setattr(templates, "_confirm_payload", lambda data: captured.update(data) or True)
    return captured


def test_build_workshop_never_sends_duration_hours(monkeypatch):
    # Regression: the API rejects durationHours as an extraneous key.
    _patch_common_prompts(monkeypatch)
    captured = _capture(monkeypatch)

    assert templates.build_workshop() is not None
    assert "durationHours" not in captured
    assert captured["eventFormat"] == "In-Person"


def test_build_workshop_drops_empty_country(monkeypatch):
    _patch_common_prompts(monkeypatch, country="")
    captured = _capture(monkeypatch)

    templates.build_workshop()

    assert "country" not in captured


def test_build_workshop_returns_none_when_not_confirmed(monkeypatch):
    _patch_common_prompts(monkeypatch)
    monkeypatch.setattr(templates, "_confirm_payload", lambda data: False)

    assert templates.build_workshop() is None


def test_build_talk_asks_for_the_event_format(monkeypatch):
    # The API accepts eventFormat on talks now, so the prompt asks for it.
    _patch_common_prompts(monkeypatch)
    captured = _capture(monkeypatch)

    templates.build_talk()

    assert captured["eventFormat"] == "In-Person"


def test_hybrid_asks_how_many_were_in_the_room(monkeypatch):
    _patch_common_prompts(
        monkeypatch, event_format="Hybrid", counts={"In-person attendees": 80, "Number of attendees": 200}
    )
    captured = _capture(monkeypatch)

    templates.build_talk()

    assert captured["eventFormat"] == "Hybrid"
    assert captured["inPersonAttendees"] == 80
    assert captured["metrics"] == {"attendees": 200}


def test_zero_attendees_means_leave_the_metric_out(monkeypatch):
    # Regression: pressing Enter on "Number of attendees" sent attendees=0, and
    # the API rejects 0 ("0 is not greater or equal to 1").
    _patch_common_prompts(monkeypatch)
    captured = _capture(monkeypatch)

    templates.build_talk()

    assert "metrics" not in captured


def test_typed_attendees_are_sent(monkeypatch):
    _patch_common_prompts(monkeypatch, counts={"Number of attendees": 475})
    captured = _capture(monkeypatch)

    templates.build_talk()

    assert captured["metrics"] == {"attendees": 475}


def test_build_content(monkeypatch):
    _patch_common_prompts(monkeypatch, counts={"Views": 3500})
    captured = _capture(monkeypatch)

    templates.build_content()

    assert captured["contentType"] == "Articles"
    assert captured["metrics"] == {"readers": 3500}


def test_build_story_has_no_date_and_uses_why_is_significant(monkeypatch):
    _patch_common_prompts(monkeypatch, counts={"People reached": 2500})
    captured = _capture(monkeypatch)

    templates.build_story()

    assert "activityDate" not in captured
    assert captured["whyIsSignificant"] == "<p>Body text.</p>"
    assert captured["significanceType"] == templates.SIGNIFICANCE_TYPES[4]
    assert captured["metrics"] == {"impact": 2500}


def test_build_interaction(monkeypatch):
    _patch_common_prompts(monkeypatch, counts={"Time spent": 50})
    captured = _capture(monkeypatch)

    templates.build_interaction()

    assert captured["interactionType"] == templates.INTERACTION_TYPES[0]
    assert captured["format"] == templates.INTERACTION_FORMATS[3]
    assert captured["metrics"] == {"timeSpent": 50}
    assert captured["title"] == "answer @ answer (EN-US)"


def test_build_feedback(monkeypatch):
    _patch_common_prompts(monkeypatch, counts={"Time spent": 45})
    captured = _capture(monkeypatch)

    templates.build_feedback()

    assert captured["contentType"] == "Product feedback session"
    assert captured["productDescription"] == "<p>answer</p>"
    assert captured["metrics"] == {"timeSpent": 45}


def test_build_mentoring(monkeypatch):
    _patch_common_prompts(monkeypatch, counts={"People mentored": 3})
    captured = _capture(monkeypatch)

    templates.build_mentoring()

    assert captured["metrics"] == {"attendees": 3}
    assert captured["eventFormat"] == "In-Person"
    assert captured["country"] == "Brazil"


@pytest.mark.parametrize("builder", ["build_talk", "build_content", "build_interaction", "build_feedback", "build_mentoring"])
def test_a_negative_count_is_reported_not_sent(monkeypatch, builder, capsys):
    counts = {"Number of attendees": -5, "Views": -5, "Time spent": -5, "People mentored": -5}
    _patch_common_prompts(monkeypatch, counts=counts)
    monkeypatch.setattr(templates, "_confirm_payload", lambda data: pytest.fail("must not ask to submit"))

    assert getattr(templates, builder)() is None
    assert "Problem:" in capsys.readouterr().out
