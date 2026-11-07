"""tools/check_api.py: the parsing and the drift reports, without touching the network."""

import pytest

from tools import check_api as ca

# Shape of a real answer (seen on 2026-11-07), guards included.
REAL = (
    "[#: extraneous key [zzzProbe] is not permitted, "
    "#/private: expected type: Boolean, found: String, "
    "#/title: expected maxLength: 200, actual: 250]"
)


class TestParsing:
    def test_split_violations(self):
        assert ca.split_violations(REAL) == [
            "#: extraneous key [zzzProbe] is not permitted",
            "#/private: expected type: Boolean, found: String",
            "#/title: expected maxLength: 200, actual: 250",
        ]

    def test_only_the_deliberate_ones_are_removed(self):
        assert ca.real_violations(REAL) == ["#/title: expected maxLength: 200, actual: 250"]

    def test_nothing_left_when_only_the_guards_complain(self):
        only_guards = "[#: extraneous key [zzzProbe] is not permitted, #/private: expected type: Boolean, found: String]"

        assert ca.real_violations(only_guards) == []

    def test_a_single_violation_without_brackets(self):
        assert ca.split_violations("#/title: expected minLength: 3, actual: 1") == [
            "#/title: expected minLength: 3, actual: 1"
        ]

    def test_extraneous_keys_in_brackets_do_not_confuse_the_split(self):
        text = "[#: extraneous key [durationHours] is not permitted, #: extraneous key [city] is not permitted]"

        assert len(ca.split_violations(text)) == 2

    def test_empty_text(self):
        assert ca.split_violations("") == []


class FakeProber:
    """Answers like the API: `rejects` is the set of (kind, field) pairs it refuses."""

    def __init__(self, rejects=(), reject_tags=()):
        self.rejects = set(rejects)
        self.reject_tags = set(reject_tags)
        self.calls = []

    def probe(self, kind, payload):
        self.calls.append((kind, payload))
        out = []
        for tag_index, tag in enumerate(payload.get("tags", [])):
            if tag in self.reject_tags:
                out.append(f"#/tags/{tag_index}: {tag} is not a valid enum value")
        for field in payload:
            if (kind, field) in self.rejects:
                out.append(f"#/{field}: nope")
        return out


class TestChecks:
    def test_tags_that_the_api_dropped_are_reported_by_name(self):
        gone = ca.t.SUGGESTED_TAGS[3]

        drift = ca.check_tags(FakeProber(reject_tags={gone}))

        assert drift == [f"tag no longer accepted: {gone}"]

    def test_no_tag_drift(self):
        assert ca.check_tags(FakeProber()) == []

    def test_an_enum_value_the_api_stopped_accepting(self):
        class OneBad(FakeProber):
            def probe(self, kind, payload):
                if kind == "content" and payload.get("contentType") == "Books":
                    return ["#/contentType: Books is not a valid enum value"]
                return []

        assert ca.check_enums(OneBad()) == ["content-creation: contentType no longer accepts 'Books'"]

    def test_limits_report_both_directions(self):
        class Lenient(FakeProber):
            def probe(self, kind, payload):
                return []  # accepts everything, including the over-limit probes

        drift = ca.check_limits(Lenient())

        assert any("title now accepts more than 200" in d for d in drift)
        assert any("attendees=0 is now accepted" in d for d in drift)

    def test_limits_are_clean_when_the_api_behaves(self):
        class Strict(FakeProber):
            def probe(self, kind, payload):
                limits = {"title": 200, "description": 2000, "additionalInfo": 2000, "productDescription": 500}
                for field, limit in limits.items():
                    if len(payload.get(field, "")) > limit and not (field == "title" and payload[field] == "Probe title"):
                        return [f"#/{field}: expected maxLength: {limit}"]
                if payload.get("metrics", {}).get("attendees") == 0:
                    return ["#/metrics/attendees: 0 is not greater or equal to 1"]
                return []

        assert ca.check_limits(Strict()) == []

    def test_examples_check_sends_each_example_without_the_private_guard(self):
        prober = FakeProber()

        assert ca.check_examples(prober) == []
        assert {kind for kind, _ in prober.calls} == set(ca.ENDPOINTS)
        assert all("private" not in payload for _, payload in prober.calls)

    def test_an_example_problem_names_the_file(self):
        drift = ca.check_examples(FakeProber(rejects={("talk", "eventFormat")}))

        assert drift and drift[0].startswith("talk.toml:")


class TestSafety:
    def test_every_endpoint_the_checker_knows_is_a_real_draft_endpoint(self):
        from advocu_manager import api
        import inspect

        source = inspect.getsource(api.AdvocuClient)
        for endpoint in ca.ENDPOINTS.values():
            assert f"/activity-drafts/{endpoint}" in source

    def test_the_guards_are_two_independent_violations(self):
        # If one stopped working, the other would still make the API reject the probe.
        assert "zzzProbe" in ca.GUARDS and not isinstance(ca.GUARDS["private"], bool)

    def test_an_accepted_probe_stops_everything(self):
        class Resp:
            status_code = 201
            text = '{"id": "abc"}'

        class Session:
            def post(self, *a, **k):
                return Resp()

        class Client:
            timeout = 1
            session = Session()

        prober = ca.Prober(Client())
        ca.time.sleep = lambda _s: None  # no need to wait in a test

        with pytest.raises(ca.DraftCreated, match="abc"):
            prober.probe("talk", {"title": "x"})

    def test_a_rate_limit_is_never_read_as_all_clear(self):
        class Resp:
            status_code = 429
            text = "slow down"

        class Session:
            def post(self, *a, **k):
                return Resp()

        class Client:
            timeout = 1
            session = Session()

        ca.time.sleep = lambda _s: None
        with pytest.raises(ca.UnexpectedResponse, match="429"):
            ca.Prober(Client()).probe("talk", {"title": "x"})
