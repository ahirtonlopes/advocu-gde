from unittest.mock import MagicMock

import pytest
import requests

from advocu_manager.api import BASE_URL, DEFAULT_TIMEOUT, AdvocuClient, AdvocuNetworkError


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    # The client throttles 2s between calls; tests shouldn't pay that cost.
    monkeypatch.setattr("advocu_manager.api.time.sleep", lambda _seconds: None)


def make_response(status_code=200, json_body=None, text=""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_body if json_body is not None else {}
    resp.text = text
    return resp


class TestConstruction:
    def test_requires_token(self, monkeypatch):
        monkeypatch.delenv("ADVOCU_TOKEN", raising=False)
        with pytest.raises(ValueError):
            AdvocuClient()

    def test_reads_token_from_env(self, monkeypatch):
        monkeypatch.setenv("ADVOCU_TOKEN", "env-token")
        client = AdvocuClient()
        assert client.token == "env-token"
        assert client.session.headers["Authorization"] == "Bearer env-token"

    def test_explicit_token_overrides_env(self, monkeypatch):
        monkeypatch.setenv("ADVOCU_TOKEN", "env-token")
        client = AdvocuClient(token="explicit-token")
        assert client.token == "explicit-token"


class TestRequests:
    def test_list_activities_hits_correct_url_and_params(self, monkeypatch):
        client = AdvocuClient(token="t")
        mock_get = MagicMock(return_value=make_response(json_body={"content": []}))
        monkeypatch.setattr(client.session, "get", mock_get)

        client.list_activities(page=2, size=50)

        mock_get.assert_called_once_with(
            f"{BASE_URL}/activities", params={"page": 2, "size": 50}, timeout=DEFAULT_TIMEOUT
        )

    def test_create_talk_draft_posts_to_public_speaking_endpoint(self, monkeypatch):
        client = AdvocuClient(token="t")
        mock_post = MagicMock(return_value=make_response(json_body={"id": "abc"}))
        monkeypatch.setattr(client.session, "post", mock_post)

        result = client.create_talk_draft({"title": "x"})

        mock_post.assert_called_once_with(
            f"{BASE_URL}/activity-drafts/public-speaking", json={"title": "x"}, timeout=DEFAULT_TIMEOUT
        )
        assert result == {"id": "abc"}

    def test_create_workshop_draft_posts_to_workshop_endpoint(self, monkeypatch):
        client = AdvocuClient(token="t")
        mock_post = MagicMock(return_value=make_response(json_body={"id": "abc"}))
        monkeypatch.setattr(client.session, "post", mock_post)

        client.create_workshop_draft({"title": "x"})

        mock_post.assert_called_once_with(
            f"{BASE_URL}/activity-drafts/workshop", json={"title": "x"}, timeout=DEFAULT_TIMEOUT
        )

    def test_update_activity_wraps_fields_in_data(self, monkeypatch):
        client = AdvocuClient(token="t")
        mock_patch = MagicMock(return_value=make_response(json_body={}))
        monkeypatch.setattr(client.session, "patch", mock_patch)

        client.update_activity("id123", {"title": "New"})

        mock_patch.assert_called_once_with(
            f"{BASE_URL}/activities/id123", json={"data": {"title": "New"}}, timeout=DEFAULT_TIMEOUT
        )


class TestErrorHandling:
    def test_raises_httperror_with_json_message(self, monkeypatch):
        client = AdvocuClient(token="t")
        monkeypatch.setattr(
            client.session,
            "post",
            MagicMock(return_value=make_response(status_code=400, json_body={"message": "bad field"})),
        )

        with pytest.raises(requests.HTTPError, match="HTTP 400: bad field"):
            client.create_talk_draft({})

    def test_raises_httperror_with_plain_text_when_body_not_json(self, monkeypatch):
        client = AdvocuClient(token="t")
        bad_response = make_response(status_code=500, text="Internal Server Error")
        bad_response.json.side_effect = ValueError("not json")
        monkeypatch.setattr(client.session, "post", MagicMock(return_value=bad_response))

        with pytest.raises(requests.HTTPError, match="HTTP 500: Internal Server Error"):
            client.create_talk_draft({})


class TestPagination:
    def test_list_all_activities_stops_when_page_shorter_than_size(self, monkeypatch):
        client = AdvocuClient(token="t")
        page_response = make_response(json_body={"content": [{"id": 1}, {"id": 2}]})
        monkeypatch.setattr(client.session, "get", MagicMock(return_value=page_response))

        activities = client.list_all_activities()

        assert activities == [{"id": 1}, {"id": 2}]

    def test_list_all_activities_stops_on_empty_page(self, monkeypatch):
        client = AdvocuClient(token="t")
        monkeypatch.setattr(
            client.session, "get", MagicMock(return_value=make_response(json_body={"content": []}))
        )

        assert client.list_all_activities() == []

    def test_list_all_activities_paginates_across_multiple_pages(self, monkeypatch):
        client = AdvocuClient(token="t")
        full_page = [{"id": i} for i in range(100)]
        last_page = [{"id": 100}]
        responses = [
            make_response(json_body={"content": full_page, "totalPages": 2}),
            make_response(json_body={"content": last_page, "totalPages": 2}),
        ]
        monkeypatch.setattr(client.session, "get", MagicMock(side_effect=responses))

        activities = client.list_all_activities()

        assert len(activities) == 101


class TestTimeoutsAndNetworkErrors:
    def test_default_timeout_is_a_connect_read_pair(self):
        assert DEFAULT_TIMEOUT == (5, 30)

    def test_custom_timeout_is_forwarded(self, monkeypatch):
        client = AdvocuClient(token="t", timeout=7)
        mock_get = MagicMock(return_value=make_response(json_body={"content": []}))
        monkeypatch.setattr(client.session, "get", mock_get)

        client.list_activities()

        assert mock_get.call_args.kwargs["timeout"] == 7

    def test_timeout_becomes_friendly_error(self, monkeypatch):
        client = AdvocuClient(token="t")
        monkeypatch.setattr(
            client.session, "get", MagicMock(side_effect=requests.exceptions.ReadTimeout())
        )

        with pytest.raises(AdvocuNetworkError, match="timed out after 30s"):
            client.list_activities()

    def test_connect_timeout_is_treated_as_timeout(self, monkeypatch):
        client = AdvocuClient(token="t")
        monkeypatch.setattr(
            client.session, "post", MagicMock(side_effect=requests.exceptions.ConnectTimeout())
        )

        with pytest.raises(AdvocuNetworkError, match="timed out"):
            client.create_talk_draft({})

    def test_connection_error_becomes_friendly_error(self, monkeypatch):
        client = AdvocuClient(token="t")
        monkeypatch.setattr(
            client.session, "get", MagicMock(side_effect=requests.exceptions.ConnectionError())
        )

        with pytest.raises(AdvocuNetworkError, match="Could not connect to Advocu"):
            client.list_activities()

    def test_network_error_is_a_requests_exception(self):
        # The CLI catches requests.RequestException, so this must stay true.
        assert issubclass(AdvocuNetworkError, requests.RequestException)

    def test_non_json_success_body_is_reported(self, monkeypatch):
        client = AdvocuClient(token="t")
        bad = make_response(status_code=200)
        bad.json.side_effect = ValueError("not json")
        monkeypatch.setattr(client.session, "get", MagicMock(return_value=bad))

        with pytest.raises(AdvocuNetworkError, match="not valid JSON"):
            client.list_activities()


class TestErrorMessages:
    def test_validation_details_are_included(self, monkeypatch):
        # Real response shape seen when a workshop draft sent durationHours.
        body = {
            "message": "Activity draft did not pass validation.",
            "details": {"error": "[#: extraneous key [durationHours] is not permitted]"},
        }
        client = AdvocuClient(token="t")
        monkeypatch.setattr(
            client.session, "post", MagicMock(return_value=make_response(400, body))
        )

        with pytest.raises(requests.HTTPError) as exc:
            client.create_workshop_draft({})

        assert "Activity draft did not pass validation." in str(exc.value)
        assert "extraneous key [durationHours]" in str(exc.value)

    @pytest.mark.parametrize(
        "status, hint",
        [
            (401, "check that your token is valid"),
            (403, "not allowed"),
            (404, "check the activity id"),
            (429, "rate limit reached"),
            (500, "server error"),
            (503, "server error"),
        ],
    )
    def test_status_hints(self, monkeypatch, status, hint):
        client = AdvocuClient(token="t")
        monkeypatch.setattr(
            client.session,
            "get",
            MagicMock(return_value=make_response(status, {"message": "nope"})),
        )

        with pytest.raises(requests.HTTPError, match=f"HTTP {status}: nope") as exc:
            client.list_activities()

        assert hint in str(exc.value)

    def test_400_has_no_extra_hint(self, monkeypatch):
        client = AdvocuClient(token="t")
        monkeypatch.setattr(
            client.session, "post", MagicMock(return_value=make_response(400, {"message": "bad"}))
        )

        with pytest.raises(requests.HTTPError) as exc:
            client.create_talk_draft({})

        assert str(exc.value) == "HTTP 400: bad"

    def test_hint_alone_when_the_body_is_empty(self, monkeypatch):
        client = AdvocuClient(token="t")
        empty = make_response(401, json_body=None, text="")
        empty.json.side_effect = ValueError("no body")
        monkeypatch.setattr(client.session, "get", MagicMock(return_value=empty))

        with pytest.raises(requests.HTTPError) as exc:
            client.list_activities()

        assert str(exc.value) == (
            "HTTP 401: check that your token is valid: set ADVOCU_TOKEN or pass --token"
        )

    def test_placeholder_when_there_is_neither_body_nor_hint(self, monkeypatch):
        client = AdvocuClient(token="t")
        empty = make_response(418, json_body=None, text="")
        empty.json.side_effect = ValueError("no body")
        monkeypatch.setattr(client.session, "get", MagicMock(return_value=empty))

        with pytest.raises(requests.HTTPError) as exc:
            client.list_activities()

        assert str(exc.value) == "HTTP 418: (empty response)"
