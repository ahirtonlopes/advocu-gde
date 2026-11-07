"""Draft specs: validation, payload building and file loading (advocu submit --file)."""

from datetime import date
from pathlib import Path

import pytest

from advocu_manager.templates import (
    DESCRIPTION_MAX_LENGTH,
    INTERACTION_FORMATS,
    INTERACTION_TYPES,
    SIGNIFICANCE_TYPES,
    SUGGESTED_TAGS,
    SpecError,
    load_spec,
    payload_from_spec,
    payload_problems,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

KINDS = ["talk", "workshop", "content", "story", "interaction", "feedback", "mentoring"]

TALK = {
    "title": "Agents",
    "event": "DevFest X",
    "date": "2026-10-31",
    "url": "https://example.com/event",
    "tags": ["AI"],
}


class TestTalk:
    def test_minimal_talk_uses_the_defaults(self):
        # No attendees given: no metrics at all (the API refuses 0).
        assert payload_from_spec("talk", TALK) == {
            "title": "Speaker @ DevFest X - Agents (EN-US)",
            "activityDate": "2026-10-31",
            "activityUrl": "https://example.com/event",
            "description": "<p></p>",
            "tags": ["AI"],
            "private": False,
        }

    def test_full_talk(self):
        data = payload_from_spec(
            "talk",
            {
                **TALK,
                "role": "Keynote",
                "attendees": 120,
                "in_person_attendees": 80,
                "event_format": "hybrid",
                "language": "pt-br",
                "country": "Brazil",
                "description": "Hello **world**",
                "additional_info": "Recorded by the organisers.",
                "resources": [{"name": "Slides", "url": "https://example.com/s.pdf"}],
            },
        )

        assert data["title"] == "Keynote @ DevFest X - Agents (PT-BR)"
        assert data["metrics"] == {"attendees": 120}
        assert data["inPersonAttendees"] == 80
        assert data["eventFormat"] == "Hybrid"
        assert data["country"] == "Brazil"
        assert data["additionalInfo"] == "Recorded by the organisers."
        assert data["description"].startswith("<p>Hello <strong>world</strong></p>")
        assert '<a href="https://example.com/s.pdf" rel="nofollow">Slides</a>' in data["description"]

    def test_talk_accepts_an_event_format_but_does_not_assume_one(self):
        # The API used to reject eventFormat on public-speaking; it accepts it now.
        assert "eventFormat" not in payload_from_spec("talk", TALK)
        assert payload_from_spec("talk", {**TALK, "event_format": "Virtual"})["eventFormat"] == "Virtual"
        with pytest.raises(SpecError, match="event_format must be one of"):
            payload_from_spec("talk", {**TALK, "event_format": "Hologram"})

    def test_blank_country_is_left_out(self):
        assert "country" not in payload_from_spec("talk", {**TALK, "country": "  "})

    def test_blank_role_falls_back_to_the_default(self):
        assert payload_from_spec("talk", {**TALK, "role": ""})["title"].startswith("Speaker @")

    def test_blank_language_falls_back_to_english(self):
        assert payload_from_spec("talk", {**TALK, "language": ""})["title"].endswith("(EN-US)")


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
        # The API answers "extraneous key [durationHours]".
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
        assert "metrics" not in data
        assert "country" not in data

    def test_content_type_is_normalised(self):
        assert payload_from_spec("content", {**self.SPEC, "content_type": "videos"})["contentType"] == "Videos"

    @pytest.mark.parametrize("value", ["Books", "Newsletters", "Demos"])
    def test_every_content_type_the_api_accepts(self, value):
        assert payload_from_spec("content", {**self.SPEC, "content_type": value})["contentType"] == value

    def test_other_is_not_a_content_type_anymore(self):
        # The API answers "Other is not a valid enum value".
        with pytest.raises(SpecError, match="content_type must be one of"):
            payload_from_spec("content", {**self.SPEC, "content_type": "Other"})

    def test_uses_readers_not_attendees(self):
        assert payload_from_spec("content", {**self.SPEC, "readers": 3500})["metrics"] == {"readers": 3500}
        with pytest.raises(SpecError, match="Unknown key.*attendees"):
            payload_from_spec("content", {**self.SPEC, "attendees": 5})


class TestStory:
    SPEC = {"title": "A story", "tags": ["AI"]}

    def test_the_text_goes_to_why_is_significant_and_there_is_no_date(self):
        data = payload_from_spec("story", {**self.SPEC, "description": "Text"})

        assert data == {
            "title": "A story",
            "whyIsSignificant": "<p>Text</p>",
            "tags": ["AI"],
            "private": False,
        }

    def test_stories_have_no_date(self):
        # The API answers "extraneous key [activityDate]" for stories.
        with pytest.raises(SpecError, match="Unknown key.*date"):
            payload_from_spec("story", {**self.SPEC, "date": "2026-09-12"})

    def test_significance_and_impact(self):
        data = payload_from_spec(
            "story", {**self.SPEC, "significance_type": "community leading", "impact": 2500}
        )

        assert data["significanceType"] == "Community Leading"
        assert data["metrics"] == {"impact": 2500}

    def test_every_significance_type(self):
        for value in SIGNIFICANCE_TYPES:
            assert payload_from_spec("story", {**self.SPEC, "significance_type": value})["significanceType"] == value

    def test_no_resources_list_on_stories(self):
        with pytest.raises(SpecError, match="Unknown key.*resources"):
            payload_from_spec("story", {**self.SPEC, "resources": []})

    def test_url_is_optional_but_validated(self):
        assert payload_from_spec("story", {**self.SPEC, "url": "https://example.com/x"})["activityUrl"] == (
            "https://example.com/x"
        )
        with pytest.raises(SpecError, match="url must start with http"):
            payload_from_spec("story", {**self.SPEC, "url": "example.com"})


class TestInteraction:
    SPEC = {
        "title": "Product council",
        "date": "2026-04-08",
        "tags": ["AI"],
        "interaction_type": INTERACTION_TYPES[0],
        "format": "Online feedback sessions",
    }

    def test_payload(self):
        data = payload_from_spec(
            "interaction",
            {**self.SPEC, "event": "GDE Summit", "minutes": 50, "additional_links": "https://x.com"},
        )

        assert data == {
            "title": "Product council @ GDE Summit (EN-US)",
            "interactionType": INTERACTION_TYPES[0],
            "format": "Online feedback sessions",
            "activityDate": "2026-04-08",
            "description": "<p></p>",
            "tags": ["AI"],
            "metrics": {"timeSpent": 50},
            "additionalLinks": "https://x.com",
            "private": False,
        }

    def test_event_is_optional(self):
        assert payload_from_spec("interaction", self.SPEC)["title"] == "Product council (EN-US)"

    def test_type_and_format_are_required(self):
        spec = {k: v for k, v in self.SPEC.items() if k not in ("interaction_type", "format")}
        with pytest.raises(SpecError) as exc:
            payload_from_spec("interaction", spec)

        assert "Missing required key: interaction_type." in exc.value.errors
        assert "Missing required key: format." in exc.value.errors

    def test_values_are_normalised_and_checked(self):
        data = payload_from_spec("interaction", {**self.SPEC, "format": "ONLINE FEEDBACK SESSIONS"})
        assert data["format"] == "Online feedback sessions"
        with pytest.raises(SpecError, match="format must be one of"):
            payload_from_spec("interaction", {**self.SPEC, "format": "Hybrid"})
        with pytest.raises(SpecError, match="interaction_type must be one of"):
            payload_from_spec("interaction", {**self.SPEC, "interaction_type": "Other"})

    def test_every_value_the_api_accepts(self):
        for value in INTERACTION_FORMATS:
            assert payload_from_spec("interaction", {**self.SPEC, "format": value})["format"] == value
        for value in INTERACTION_TYPES:
            assert payload_from_spec("interaction", {**self.SPEC, "interaction_type": value})["interactionType"] == value

    def test_has_no_url_country_or_attendees(self):
        for key, value in (("url", "https://x.com"), ("country", "Brazil"), ("attendees", 3)):
            with pytest.raises(SpecError, match=f"Unknown key.*{key}"):
                payload_from_spec("interaction", {**self.SPEC, key: value})


class TestFeedback:
    SPEC = {
        "title": "Monthly feedback",
        "date": "2026-10-22",
        "tags": ["AI"],
        "product_description": "JAX: **MaxText**",
    }

    def test_payload(self):
        data = payload_from_spec("feedback", {**self.SPEC, "minutes": 45})

        assert data == {
            "title": "Monthly feedback (EN-US)",
            "contentType": "Product feedback session",
            "activityDate": "2026-10-22",
            "description": "<p></p>",
            "productDescription": "<p>JAX: <strong>MaxText</strong></p>",
            "tags": ["AI"],
            "metrics": {"timeSpent": 45},
            "private": False,
        }

    def test_content_type_choices(self):
        assert payload_from_spec("feedback", {**self.SPEC, "content_type": "early access program"})[
            "contentType"
        ] == "Early access program"
        with pytest.raises(SpecError, match="content_type must be one of"):
            payload_from_spec("feedback", {**self.SPEC, "content_type": "Articles"})

    def test_product_description_is_required(self):
        spec = {k: v for k, v in self.SPEC.items() if k != "product_description"}
        with pytest.raises(SpecError, match="Missing required key: product_description"):
            payload_from_spec("feedback", spec)

    def test_product_description_is_capped_at_500_rendered_characters(self):
        data = payload_from_spec("feedback", {**self.SPEC, "product_description": "x" * 600})

        errors, _ = payload_problems(data)

        assert any("product_description" in e and "500" in e for e in errors)


class TestMentoring:
    SPEC = {"title": "Mentoring devs", "date": "2026-09-12", "tags": ["AI"]}

    def test_minimal(self):
        assert payload_from_spec("mentoring", self.SPEC) == {
            "title": "Mentoring devs (EN-US)",
            "activityDate": "2026-09-12",
            "description": "<p></p>",
            "tags": ["AI"],
            "private": False,
        }

    def test_full(self):
        data = payload_from_spec(
            "mentoring",
            {
                **self.SPEC,
                "url": "https://example.com/program",
                "attendees": 3,
                "event_format": "virtual",
                "country": "Brazil",
                "language": "PT-BR",
            },
        )

        assert data["title"] == "Mentoring devs (PT-BR)"
        assert data["activityUrl"] == "https://example.com/program"
        assert data["metrics"] == {"attendees": 3}
        assert data["eventFormat"] == "Virtual"
        assert data["country"] == "Brazil"

    def test_there_is_no_default_format(self):
        assert "eventFormat" not in payload_from_spec("mentoring", self.SPEC)


class TestCounts:
    @pytest.mark.parametrize("kind, key", [("talk", "attendees"), ("content", "readers"), ("story", "impact"), ("interaction", "minutes")])
    def test_zero_is_refused_with_advice(self, kind, key):
        # The API answers "0 is not greater or equal to 1" for every metric.
        spec = {
            "talk": TALK,
            "content": {"title": "T t", "date": "2026-01-01", "url": "https://x.com", "tags": ["AI"]},
            "story": {"title": "T t", "tags": ["AI"]},
            "interaction": TestInteraction.SPEC,
        }[kind]

        with pytest.raises(SpecError, match=f"{key} must be a whole number, 1 or more \\(leave it out if unknown\\)"):
            payload_from_spec(kind, {**spec, key: 0})

    def test_null_means_not_given(self):
        data = payload_from_spec("talk", {**TALK, "attendees": None, "event_format": None})

        assert "metrics" not in data
        assert "eventFormat" not in data

    def test_in_person_attendees_may_be_zero_but_not_negative(self):
        assert payload_from_spec("talk", {**TALK, "in_person_attendees": 0})["inPersonAttendees"] == 0
        with pytest.raises(SpecError, match="in_person_attendees must be a whole number, 0 or more"):
            payload_from_spec("talk", {**TALK, "in_person_attendees": -1})

    def test_boolean_is_not_a_count(self):
        with pytest.raises(SpecError, match="attendees must be a whole number"):
            payload_from_spec("talk", {**TALK, "attendees": True})

    def test_a_float_is_not_a_count(self):
        with pytest.raises(SpecError, match="attendees must be a whole number"):
            payload_from_spec("talk", {**TALK, "attendees": 1.5})


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

    @pytest.mark.parametrize("kind", KINDS)
    def test_private_is_always_false(self, kind):
        spec = {
            "talk": TALK, "workshop": TALK,
            "content": {"title": "T t", "date": "2026-01-01", "url": "https://x.com", "tags": ["AI"]},
            "story": {"title": "T t", "tags": ["AI"]},
            "interaction": TestInteraction.SPEC, "feedback": TestFeedback.SPEC,
            "mentoring": TestMentoring.SPEC,
        }[kind]

        assert payload_from_spec(kind, spec)["private"] is False


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

    def test_a_story_text_over_the_limit_is_an_error_too(self):
        data = payload_from_spec("story", {"title": "A story", "tags": ["AI"], "description": "x" * 2500})

        errors, _ = payload_problems(data)

        assert len(errors) == 1 and "2000" in errors[0]

    def test_title_length_is_checked_on_the_final_title(self):
        long_title = payload_from_spec("talk", {**TALK, "title": "T" * 190})  # + role, event, language > 200
        short_title = payload_from_spec("story", {"title": "ab", "tags": ["AI"]})

        assert any("title is" in e for e in payload_problems(long_title)[0])
        assert any("title is 2 characters" in e for e in payload_problems(short_title)[0])

    def test_additional_info_over_the_limit_is_an_error(self):
        data = payload_from_spec("talk", {**TALK, "additional_info": "x" * 2001})

        assert any("additional_info" in e for e in payload_problems(data)[0])

    def test_unknown_tag_is_only_a_warning(self):
        data = payload_from_spec("talk", {**TALK, "tags": ["AI", "Nonexistent-Tag"]})

        errors, warnings = payload_problems(data)

        assert errors == []
        assert len(warnings) == 1 and "Nonexistent-Tag" in warnings[0]

    def test_a_tag_the_api_dropped_now_warns(self):
        # "Cloud - Data" was in the list until the Cloud tags were reorganised.
        data = payload_from_spec("talk", {**TALK, "tags": ["Cloud - Data"]})

        assert payload_problems(data)[1]

    def test_in_person_event_without_country_warns(self):
        data = payload_from_spec("talk", {**TALK, "event_format": "In-Person"})

        assert any("country" in w for w in payload_problems(data)[1])

    def test_virtual_event_needs_no_country(self):
        assert payload_problems(payload_from_spec("talk", {**TALK, "event_format": "Virtual"})) == ([], [])

    def test_hybrid_without_in_person_attendees_warns(self):
        data = payload_from_spec("talk", {**TALK, "event_format": "Hybrid", "country": "Brazil"})

        assert any("in_person_attendees" in w for w in payload_problems(data)[1])

    def test_more_people_in_the_room_than_in_total_warns(self):
        data = payload_from_spec(
            "talk", {**TALK, "attendees": 10, "in_person_attendees": 50, "event_format": "Virtual"}
        )

        assert any("larger than attendees" in w for w in payload_problems(data)[1])


class TestTagList:
    def test_no_duplicates(self):
        assert len(SUGGESTED_TAGS) == len(set(SUGGESTED_TAGS))

    def test_tags_the_api_dropped_are_gone(self):
        # Rejected by the API on 2026-11-07, as reported by tools/check_api.py.
        for gone in ("Cloud - Data", "Cloud - Security", "AR/VR", "Dart - Flutter", "AI - Gemini Enterprise Agent Platform"):
            assert gone not in SUGGESTED_TAGS


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.*")), ids=lambda p: p.name)
def test_every_example_file_is_valid(path):
    """The examples are documentation: they must keep working."""
    data = payload_from_spec(path.stem, load_spec(path))

    assert payload_problems(data) == ([], [])


def test_there_is_an_example_for_each_draft_type():
    assert {p.stem for p in EXAMPLES.glob("*.*")} == set(KINDS)
