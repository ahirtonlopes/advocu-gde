from __future__ import annotations

import os
import time
import requests

BASE_URL = "https://api.advocu.com/personal-api/v1/gde"
RATE_LIMIT_DELAY = 60 / 30  # 30 req/min → 2s between requests

# (connect, read) in seconds. Without a timeout, requests waits forever on a
# dead connection and the CLI just hangs.
DEFAULT_TIMEOUT = (5, 30)

_STATUS_HINTS = {
    401: "check that your token is valid: set ADVOCU_TOKEN or pass --token",
    403: "your token is not allowed to do this",
    404: "not found, check the activity id",
    429: "rate limit reached (30 requests/min), wait a minute and retry",
}


class AdvocuNetworkError(requests.RequestException):
    """Advocu could not be reached, timed out, or sent back something unreadable."""


class AdvocuClient:
    def __init__(self, token: str | None = None, timeout=DEFAULT_TIMEOUT):
        self.token = token or os.environ.get("ADVOCU_TOKEN", "")
        if not self.token:
            raise ValueError(
                "Token not found. Set the ADVOCU_TOKEN environment variable "
                "or pass --token on the command line."
            )
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request = time.time()

    def _raise(self, resp: requests.Response):
        try:
            body = resp.json()
            msg = body.get("message") or body.get("error") or ""
            # Validation failures put the useful part (which field, which rule)
            # in details.error, e.g. "extraneous key [durationHours] ...".
            details = body.get("details")
            detail = details.get("error") if isinstance(details, dict) else None
            if isinstance(detail, str) and detail:
                msg = f"{msg} {detail}".strip()
        except Exception:
            msg = resp.text[:200] if resp.text else ""

        hint = _STATUS_HINTS.get(resp.status_code)
        if hint is None and resp.status_code >= 500:
            hint = "Advocu had a server error, try again in a few minutes"
        text = f"{msg} ({hint})" if msg and hint else (msg or hint or "(empty response)")
        raise requests.HTTPError(f"HTTP {resp.status_code}: {text}", response=resp)

    def _read_timeout(self) -> float:
        return self.timeout[1] if isinstance(self.timeout, tuple) else self.timeout

    def _call(self, method: str, path: str, **kwargs):
        self._throttle()
        try:
            resp = getattr(self.session, method)(
                f"{BASE_URL}{path}", timeout=self.timeout, **kwargs
            )
        except requests.exceptions.Timeout as e:
            raise AdvocuNetworkError(
                f"The request to Advocu timed out after {self._read_timeout():g}s. "
                "Check your connection and try again."
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise AdvocuNetworkError(
                "Could not connect to Advocu (api.advocu.com). "
                "Check your internet connection and try again."
            ) from e

        if not resp.ok:
            self._raise(resp)
        try:
            return resp.json()
        except ValueError as e:
            raise AdvocuNetworkError(
                "Advocu returned a response that is not valid JSON."
            ) from e

    def _get(self, path: str, **params):
        return self._call("get", path, params=params)

    def _patch(self, path: str, payload: dict):
        return self._call("patch", path, json=payload)

    def _post(self, path: str, payload: dict):
        return self._call("post", path, json=payload)

    # ── Activities ──────────────────────────────────────────────────────────

    def list_activities(self, page: int = 0, size: int = 100) -> dict:
        return self._get("/activities", page=page, size=size)

    def list_all_activities(self) -> list[dict]:
        activities = []
        page = 0
        while True:
            data = self.list_activities(page=page, size=100)
            items = data if isinstance(data, list) else data.get("content", [])
            if not items:
                break
            activities.extend(items)
            total_pages = data.get("totalPages") if isinstance(data, dict) else None
            if total_pages is not None and page + 1 >= total_pages:
                break
            if len(items) < 100:
                break
            page += 1
        return activities

    def update_activity(self, activity_id: str, fields: dict) -> dict:
        # PATCH espera {"data": {...}} para campos aninhados
        return self._patch(f"/activities/{activity_id}", {"data": fields})

    # ── Drafts ──────────────────────────────────────────────────────────────

    def create_content_draft(self, payload: dict) -> dict:
        return self._post("/activity-drafts/content-creation", payload)

    def create_talk_draft(self, payload: dict) -> dict:
        return self._post("/activity-drafts/public-speaking", payload)

    def create_workshop_draft(self, payload: dict) -> dict:
        return self._post("/activity-drafts/workshop", payload)

    def create_story_draft(self, payload: dict) -> dict:
        return self._post("/activity-drafts/stories", payload)
