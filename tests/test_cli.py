from click.testing import CliRunner

from advocu_manager import __version__
from advocu_manager.cli import cli


def test_version_flag_prints_package_version():
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"advocu, version {__version__}"


def test_short_version_flag():
    result = CliRunner().invoke(cli, ["-V"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_is_a_real_version_not_unknown():
    assert __version__ != "unknown"
    assert all(part.isdigit() for part in __version__.split("."))


class _FailingClient:
    """Stands in for AdvocuClient; every call fails with the given exception."""

    exc: Exception = RuntimeError("unset")

    def __init__(self, token=None, **kwargs):
        pass

    def list_all_activities(self):
        raise self.exc


def _run_failing(monkeypatch, exc, args=("list",)):
    import advocu_manager.cli as cli_module

    monkeypatch.setattr(cli_module, "AdvocuClient", type("C", (_FailingClient,), {"exc": exc}))
    return CliRunner().invoke(cli, ["--token", "t", *args])


def test_api_error_shows_one_line_not_a_traceback(monkeypatch):
    import requests

    result = _run_failing(monkeypatch, requests.HTTPError("HTTP 401: bad token (check your token)"))

    assert result.exit_code == 1
    assert "Error: HTTP 401: bad token" in result.output
    assert "Traceback" not in result.output


def test_network_error_shows_one_line_not_a_traceback(monkeypatch):
    from advocu_manager.api import AdvocuNetworkError

    result = _run_failing(monkeypatch, AdvocuNetworkError("Could not connect to Advocu"))

    assert result.exit_code == 1
    assert "Error: Could not connect to Advocu" in result.output
    assert "Traceback" not in result.output


def test_api_text_with_brackets_is_shown_verbatim(monkeypatch):
    # rich would swallow "[durationHours]" as a markup tag; click must not.
    import requests

    result = _run_failing(
        monkeypatch, requests.HTTPError("HTTP 400: [#: extraneous key [durationHours] is not permitted]")
    )

    assert "[durationHours]" in result.output


def test_error_is_handled_for_other_commands_too(monkeypatch):
    import requests

    result = _run_failing(monkeypatch, requests.HTTPError("HTTP 500: boom"), args=("stats",))

    assert result.exit_code == 1
    assert "Error: HTTP 500: boom" in result.output


# ── advocu submit <kind> --file ───────────────────────────────────────────────

import pytest  # noqa: E402

EXAMPLES = __import__("pathlib").Path(__file__).resolve().parent.parent / "examples"

TALK_TOML = """\
title = "Agents"
event = "DevFest X"
date = 2026-10-31
url = "https://example.com/event"
attendees = 50
language = "PT-BR"
tags = ["AI"]
description = "Hello"
"""


@pytest.fixture
def talk_file(tmp_path):
    path = tmp_path / "talk.toml"
    path.write_text(TALK_TOML, encoding="utf-8")
    return path


@pytest.fixture
def fake_api(monkeypatch):
    """Replaces AdvocuClient; records what is created and when it is built."""
    import advocu_manager.cli as cli_module

    state = {"built": 0, "created": []}

    class FakeClient:
        def __init__(self, token=None, **kwargs):
            state["built"] += 1

        def create_talk_draft(self, payload):
            state["created"].append(("talk", payload))
            return {"id": "talk-1"}

        def create_workshop_draft(self, payload):
            state["created"].append(("workshop", payload))
            return {"id": "workshop-1"}

        def create_content_draft(self, payload):
            state["created"].append(("content", payload))
            return {"id": "content-1"}

        def create_story_draft(self, payload):
            state["created"].append(("story", payload))
            return {"id": "story-1"}

        def create_interaction_draft(self, payload):
            state["created"].append(("interaction", payload))
            return {"id": "interaction-1"}

        def create_feedback_draft(self, payload):
            state["created"].append(("feedback", payload))
            return {"id": "feedback-1"}

        def create_mentoring_draft(self, payload):
            state["created"].append(("mentoring", payload))
            return {"id": "mentoring-1"}

    monkeypatch.setattr(cli_module, "AdvocuClient", FakeClient)
    return state


def run(*args, input=None):
    return CliRunner().invoke(cli, ["--token", "t", *args], input=input)


def test_dry_run_previews_and_sends_nothing(fake_api, talk_file, monkeypatch):
    monkeypatch.delenv("ADVOCU_TOKEN", raising=False)

    result = CliRunner().invoke(cli, ["submit", "talk", "--file", str(talk_file), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Dry run" in result.output
    assert "Speaker @ DevFest X - Agents (PT-BR)" in result.output
    # Works offline and without a token: the client is never even built.
    assert fake_api["built"] == 0
    assert fake_api["created"] == []


def test_yes_sends_the_draft_without_asking(fake_api, talk_file):
    result = run("submit", "talk", "--file", str(talk_file), "--yes")

    assert result.exit_code == 0, result.output
    assert "Draft created" in result.output and "talk-1" in result.output
    [(kind, payload)] = fake_api["created"]
    assert kind == "talk"
    assert payload["title"] == "Speaker @ DevFest X - Agents (PT-BR)"
    assert payload["activityDate"] == "2026-10-31"
    assert payload["metrics"] == {"attendees": 50}


def test_without_yes_it_asks_and_no_cancels(fake_api, talk_file):
    result = run("submit", "talk", "--file", str(talk_file), input="n\n")

    assert result.exit_code == 0
    assert "Cancelled." in result.output
    assert fake_api["created"] == []


def test_without_yes_it_asks_and_yes_sends(fake_api, talk_file):
    result = run("submit", "talk", "--file", str(talk_file), input="y\n")

    assert result.exit_code == 0, result.output
    assert len(fake_api["created"]) == 1


def test_invalid_file_lists_every_problem_and_sends_nothing(fake_api, tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text('title = "T"\ndate = "nope"\ntypo = 1\ntags = ["AI"]\nurl = "https://e.com"\n')

    result = run("submit", "talk", "--file", str(path), "--yes")

    assert result.exit_code == 1
    assert "bad.toml is not a valid talk draft" in result.output
    assert "Missing required key: event." in result.output
    assert "Unknown key(s): typo" in result.output
    assert "date must be a real date" in result.output
    assert fake_api["created"] == []


def test_malformed_file_and_wrong_extension(fake_api, tmp_path):
    broken = tmp_path / "broken.toml"
    broken.write_text("title = ")
    yaml = tmp_path / "talk.yaml"
    yaml.write_text("title: T")

    assert "is not valid TOML" in run("submit", "talk", "--file", str(broken), "--dry-run").output
    assert "use a .json or .toml" in run("submit", "talk", "--file", str(yaml), "--dry-run").output
    assert fake_api["created"] == []


def test_description_over_the_limit_blocks_even_with_yes(fake_api, tmp_path):
    path = tmp_path / "long.toml"
    path.write_text(TALK_TOML.replace('description = "Hello"', f'description = "{"x" * 2500}"'))

    sent = run("submit", "talk", "--file", str(path), "--yes")
    dry = run("submit", "talk", "--file", str(path), "--dry-run")

    for result in (sent, dry):
        assert result.exit_code == 1
        assert "2000" in result.output
    assert fake_api["created"] == []


def test_unknown_tag_warns_but_still_sends(fake_api, tmp_path):
    path = tmp_path / "tag.toml"
    path.write_text(TALK_TOML.replace('tags = ["AI"]', 'tags = ["AI", "Nonexistent-Tag"]'))

    result = run("submit", "talk", "--file", str(path), "--yes")

    assert result.exit_code == 0, result.output
    assert "Warning" in result.output and "Nonexistent-Tag" in result.output
    assert len(fake_api["created"]) == 1


def test_dry_run_and_yes_need_a_file(fake_api):
    for flag in ("--dry-run", "--yes"):
        result = run("submit", "talk", flag)

        assert result.exit_code == 2
        assert "only apply together with --file" in result.output


def test_missing_file_is_a_usage_error(fake_api, tmp_path):
    result = run("submit", "talk", "--file", str(tmp_path / "nope.toml"), "--dry-run")

    assert result.exit_code == 2
    assert "does not exist" in result.output


@pytest.mark.parametrize(
    "kind, filename",
    [
        ("talk", "talk.toml"),
        ("workshop", "workshop.toml"),
        ("content", "content.json"),
        ("story", "story.toml"),
        ("interaction", "interaction.toml"),
        ("feedback", "feedback.toml"),
        ("mentoring", "mentoring.toml"),
    ],
)
def test_each_kind_goes_to_its_own_endpoint(fake_api, kind, filename):
    result = run("submit", kind, "--file", str(EXAMPLES / filename), "--yes")

    assert result.exit_code == 0, result.output
    assert [k for k, _ in fake_api["created"]] == [kind]


def test_api_rejection_while_sending_is_a_one_line_error(monkeypatch, talk_file):
    import requests

    import advocu_manager.cli as cli_module

    class Rejecting:
        def __init__(self, token=None, **kwargs):
            pass

        def create_talk_draft(self, payload):
            raise requests.HTTPError(
                "HTTP 400: Activity draft did not pass validation. [#: extraneous key [durationHours]]"
            )

    monkeypatch.setattr(cli_module, "AdvocuClient", Rejecting)

    result = run("submit", "talk", "--file", str(talk_file), "--yes")

    assert result.exit_code == 1
    assert "Error: HTTP 400: Activity draft did not pass validation." in result.output
    assert "[durationHours]" in result.output
    assert "Traceback" not in result.output


def test_a_story_with_a_date_gets_a_clear_message(fake_api, tmp_path):
    # The API has no date for stories (activityDate is rejected).
    path = tmp_path / "story.toml"
    path.write_text('title = "A story"\ndate = 2026-09-12\ntags = ["AI"]\n')

    result = run("submit", "story", "--file", str(path), "--dry-run")

    assert result.exit_code == 1
    assert "Unknown key(s): date" in result.output
    assert fake_api["created"] == []


def test_zero_attendees_in_a_file_is_refused_with_advice(fake_api, tmp_path):
    path = tmp_path / "talk.toml"
    path.write_text(TALK_TOML.replace("attendees = 50", "attendees = 0"))

    result = run("submit", "talk", "--file", str(path), "--dry-run")

    assert result.exit_code == 1
    assert "leave it out if unknown" in result.output


def test_the_help_lists_all_seven_kinds():
    result = CliRunner().invoke(cli, ["submit", "--help"])

    for kind in ("talk", "workshop", "content", "story", "interaction", "feedback", "mentoring"):
        assert kind in result.output
