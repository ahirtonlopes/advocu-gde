from __future__ import annotations

import os
import time
import requests

BASE_URL = "https://api.advocu.com/personal-api/v1/gde"
RATE_LIMIT_DELAY = 60 / 30  # 30 req/min → 2s between requests


class AdvocuClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("ADVOCU_TOKEN", "")
        if not self.token:
            raise ValueError(
                "Token not found. Set the ADVOCU_TOKEN environment variable "
                "or pass --token on the command line."
            )
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
            msg = body.get("message") or body.get("error") or "(sem mensagem)"
        except Exception:
            msg = resp.text[:200] if resp.text else "(resposta vazia)"
        raise requests.HTTPError(
            f"HTTP {resp.status_code}: {msg}", response=resp
        )

    def _get(self, path: str, **params):
        self._throttle()
        resp = self.session.get(f"{BASE_URL}{path}", params=params)
        if not resp.ok:
            self._raise(resp)
        return resp.json()

    def _patch(self, path: str, payload: dict):
        self._throttle()
        resp = self.session.patch(f"{BASE_URL}{path}", json=payload)
        if not resp.ok:
            self._raise(resp)
        return resp.json()

    def _post(self, path: str, payload: dict):
        self._throttle()
        resp = self.session.post(f"{BASE_URL}{path}", json=payload)
        if not resp.ok:
            self._raise(resp)
        return resp.json()

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
