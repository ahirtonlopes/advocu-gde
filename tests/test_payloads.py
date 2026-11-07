"""Draft specs: validation, payload building and file loading (advocu submit --file)."""

from datetime import date
from pathlib import Path

import pytest

from advocu_manager.templates import (
    DESCRIPTION_MAX_LENGTH,
    SpecError,
    load_spec,
    payload_from_spec,
    payload_problems,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

TALK = {
    "title": "Agents",
    "event": "DevFest X",
    "date": "2026-10-31",
    "url": "https://example.com/event",
    "tags": ["AI"],
}


class TestTalk:
    def test_minimal_talk_uses_the_defaults(self):
        assert payload_from_spec("talk", TALK) == {
            "title": "Speaker @ DevFest X - Agents (EN-US)",
            "activityDate": "2026-10-31",
            "activityUrl": "https://example.com/event",
            "description": "<p></p>",
            "tags": ["AI"],
            "metrics": {"attendees": 0},
            "private": False,
        }

    def test_full_talk(self):
        data = payload_from_spec(
            "talk",
            {
                **TALK,
                "role": "Keynote",
                "attendees": 120,
                "language": "pt-br",
                "country": "Brazil",
                "description": "Hello **world**",
                "resources": [{"name": "Slides", "url": "https://example.com/s.pdf"}],
            },
        )

        assert data["title"] == "Keynote @ DevFest X - Agents (PT-BR)"
        assert data["metrics"] == {"attendees": 120}
        assert data["country"] == "Brazil"
        assert data["description"].startswith("<p>Hello <strong>world</strong></p>")
        assert '<a href="https://example.com/s.pdf" rel="nofollow">Slides</a>' in data["description"]

    def test_talk_never_sends_event_format(self):
        # eventFormat is rejected by /activity-drafts/public-speaking.
        assert "eventFormat" not in payload_from_spec("talk", TALK)
        with pytest.raises(SpecError, match="Unknown key"):
            payload_from_spec("talk", {**TALK, "event_format": "Hybrid"})

    def test_blank_country_is_left_out(self):
        assert "country" not in payload_from_spec("talk", {**TALK, "country": "  "})

    def test_blank_role_falls_back_to_the_default(self):
        assert payload_from_spec("talk", {**TALK, "role": ""})["title"].startswith("Speaker @")


class TestWorkshop:
    def test_defaults(self):
        data = payload_from_spec("workshop", TALK)

        assert data["title"] == "Workshop Proctor @ DevFest X - Agents (EN-US)"
        assert data["eventFormat"] == "In-Person"

    def test_event_format_is_normalised(self):
        assert payload_from_spec("workshop", {**TALK, "event_format": "hybrid"})["eventFormat"] == "Hybrid"

    def test_invalid_event_format(self):
        with pytest.raises(SpecError, match="event_format must be one of"):
            payload_from_spec("workshop", {**TALK, "event_format": "Hologram"})

    def test_duration_hours_is_rejected_like_the_api_does(self):
        # The API answers "extraneous key [durationHours]" for workshops.
        with pytest.raises(SpecError, match="Unknown key.*durationHours"):
            payload_from_spec("workshop", {**TALK, "durationHours": 2})


class TestContent:
    SPEC = {
        "title": "Intro to Gemini",
        "date": "2026-05-10",
        "url": "https://example.com/video",
        "tags": ["AI"],
    }

    def test_defaults(self):
        data = payload_from_spec("content", self.SPEC)

        assert data["title"] == "Intro to Gemini (EN-US)"
        assert data["contentType"] == "Articles"
        assert data["metrics"] == {"readers": 0}
        assert "country" not in data

    def test_content_type_is_normalised(self):
        assert payload_from_spec("content", {**self.SPEC, "content_type": "videos"})["contentType"] == "Videos"

    def test_invalid_content_type(self):
        with pytest.raises(SpecError, match="content_type must be one of"):
            payload_from_spec("content", {**self.SPEC, "content_type": "Tweet"})

    def test_uses_readers_not_attendees(self):
        assert payload_from_spec("content", {**self.SPEC, "readers": 3500})["metrics"] == {"readers": 3500}
        with pytest.raises(SpecError, match="Unknown key.*attendees"):
            payload_from_spec("content", {**self.SPEC, "attendees": 5})


class TestStory:
    SPEC = {"title": "A story", "date": "2026-09-12", "tags": ["AI"]}

    def test_story_has_no_metrics_or_resources(self):
        data = payload_from_spec("story", {**self.SPEC, "description": "Text"})

        assert data == {
            "title": "A story",
            "activityDate": "2026-09-12",
            "description": "<p>Text</p>",
            "tags": ["AI"],
            "private": False,
        }
        with pytest.raises(SpecError, match="Unknown key.*resources"):
            payload_from_spec("story", {**self.SPEC, "resources": []})

    def test_url_is_optional_but_validated(self):
        assert payload_from_spec("story", {**self.SPEC, "url": "https://example.com/x"})["activityUrl"] == (
            "https://example.com/x"
        )
        with pytest.raises(SpecError, match="url must start with http"):
            payload_from_spec("story", {**self.SPEC, "url": "example.com"})


class TestValidation:
    def test_missing_required_keys_are_all_reported(self):
        with pytest.raises(SpecError) as exc:
            payload_from_spec("talk", {})

        for key in ("title", "event", "date", "url", "tags"):
            assert f"Missing required key: {key}." in exc.value.errors

    def test_typo_in_a_key_is_caught_and_the_allowed_keys_listed(self):
        with pytest.raises(SpecError) as exc:
            payload_from_spec("talk", {**TALK, "atendees": 5})

        message = " ".join(exc.value.errors)
        assert "Unknown key(s): atendees" in message
        assert "attendees" in message  # listed among the allowed keys

    def test_every_problem_is_reported_in_one_pass(self):
        spec = {
            **TALK,
            "date": "2026-13-45",
            "url": "ftp://example.com",
            "language": "klingon",
            "attendees": -1,
            "tags": "AI",
            "resources": [{"name": "no url"}],
        }

        with pytest.raises(SpecError) as exc:
            payload_from_spec("talk", spec)

        joined = "\n".join(exc.value.errors)
        for fragment in ("date must be", "url must start", "language must be",
                         "attendees must be", "tags must be", "resources #1"):
            assert fragment in joined
        assert len(exc.value.errors) == 6

    @pytest.mark.parametrize("bad", ["20261031", "2026-02-30", "31/10/2026", "2026-W44-5", "", 20261031])
    def test_strict_dates(self, bad):
        with pytest.raises(SpecError, match="date"):
            payload_from_spec("talk", {**TALK, "date": bad})

    def test_native_toml_date_is_accepted(self):
        assert payload_from_spec("talk", {**TALK, "date": date(2026, 10, 31)})["activityDate"] == "2026-10-31"

    def test_boolean_is_not_a_count(self):
        with pytest.raises(SpecError, match="attendees must be a whole number"):
            payload_from_spec("talk", {**TALK, "attendees": True})

    def test_blank_tag_is_rejected(self):
        with pytest.raises(SpecError, match="tags must be"):
            payload_from_spec("talk", {**TALK, "tags": ["AI", "  "]})

    def test_text_fields_must_be_text(self):
        with pytest.raises(SpecError, match="description must be text"):
            payload_from_spec("talk", {**TALK, "description": 5})

    def test_unknown_kind_and_non_dict_spec(self):
        with pytest.raises(SpecError, match="Unknown draft type"):
            payload_from_spec("panel", TALK)
        with pytest.raises(SpecError, match="key = value"):
            payload_from_spec("talk", ["not", "a", "dict"])

    def test_resources_are_escaped(self):
        data = payload_from_spec(
            "talk",
            {**TALK, "resources": [{"name": "Tools & Memory", "url": "https://x.com/a?b=1&c=2"}]},
        )

        assert "Tools &amp; Memory" in data["description"]
        assert 'href="https://x.com/a?b=1&amp;c=2"' in data["description"]

    def test_identifiers_with_underscores_survive_the_whole_pipeline(self):
        data = payload_from_spec(
            "talk",
            {**TALK, "description": "Stop with exit_loop, guard with before_tool_callback."},
        )

        assert "exit_loop" in data["description"]
        assert "before_tool_callback" in data["description"]
        assert "<em>" not in data["description"]


class TestLoadSpec:
    def test_json(self, tmp_path):
        path = tmp_path / "d.json"
        path.write_text('{"title": "T"}', encoding="utf-8")

        assert load_spec(path) == {"title": "T"}

    def test_toml_with_native_date(self, tmp_path):
        path = tmp_path / "d.toml"
        path.write_text('title = "T"\ndate = 2026-10-31\n', encoding="utf-8")

        assert load_spec(path) == {"title": "T", "date": date(2026, 10, 31)}

    def test_extension_is_case_insensitive(self, tmp_path):
        path = tmp_path / "d.JSON"
        path.write_text("{}", encoding="utf-8")

        assert load_spec(path) == {}

    def test_unsupported_extension(self, tmp_path):
        path = tmp_path / "d.yaml"
        path.write_text("title: T", encoding="utf-8")

        with pytest.raises(SpecError, match="use a .json or .toml"):
            load_spec(path)

    def test_missing_file(self, tmp_path):
        with pytest.raises(SpecError, match="Could not read"):
            load_spec(tmp_path / "nope.json")

    def test_invalid_json_and_toml(self, tmp_path):
        bad_json = tmp_path / "d.json"
        bad_json.write_text("{oops", encoding="utf-8")
        bad_toml = tmp_path / "d.toml"
        bad_toml.write_text("title = ", encoding="utf-8")

        with pytest.raises(SpecError, match="is not valid JSON"):
            load_spec(bad_json)
        with pytest.raises(SpecError, match="is not valid TOML"):
            load_spec(bad_toml)

    def test_top_level_must_be_an_object(self, tmp_path):
        path = tmp_path / "d.json"
        path.write_text("[1, 2]", encoding="utf-8")

        with pytest.raises(SpecError, match="top level"):
            load_spec(path)


class TestPayloadProblems:
    def test_clean_payload(self):
        assert payload_problems(payload_from_spec("talk", TALK)) == ([], [])

    def test_description_over_the_limit_is_an_error(self):
        data = payload_from_spec("talk", {**TALK, "description": "x" * 2500})

        errors, warnings = payload_problems(data)

        assert len(errors) == 1
        assert str(DESCRIPTION_MAX_LENGTH) in errors[0]
        assert warnings == []

    def test_unknown_tag_is_only_a_warning(self):
        data = payload_from_spec("talk", {**TALK, "tags": ["AI", "Nonexistent-Tag"]})

        errors, warnings = payload_problems(data)

        assert errors == []
        assert len(warnings) == 1 and "Nonexistent-Tag" in warnings[0]


@pytest.mark.parametrize(
    "path", sorted(EXAMPLES.glob("*.*")), ids=lambda p: p.name
)
def test_every_example_file_is_valid(path):
    """The examples are documentation: they must keep working."""
    kind = {"talk": "talk", "workshop": "workshop", "content": "content", "story": "story"}[path.stem]

    data = payload_from_spec(kind, load_spec(path))

    assert payload_problems(data) == ([], [])


def test_there_is_an_example_for_each_draft_type():
    assert {p.stem for p in EXAMPLES.glob("*.*")} == {"talk", "workshop", "content", "story"}
