"""Check what this project believes about the Advocu API against the live API.

Advocu changes tags, allowed values and field rules without notice. Within a few
months the Cloud tags were reorganised and talks started accepting eventFormat,
and the docs here had not kept up. This script asks the real API instead.

It never creates anything. Every request carries two deliberate violations (a
key that does not exist and a value of the wrong type), so the API answers 400
and lists every problem it sees; only the violations that are NOT the deliberate
ones are reported.

NEVER send an empty or a valid payload to /activity-drafts/*: the API accepts it
(HTTP 201) and leaves a draft in the account. If a request is ever accepted, this
script stops at once and prints the draft id.

    ADVOCU_TOKEN=... python tools/check_api.py

Exit code: 0 no drift, 1 drift found, 2 a draft was created by mistake,
3 the check could not finish (network, rate limit, unexpected answer).
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import advocu_manager.templates as t  # noqa: E402
from advocu_manager.api import BASE_URL, AdvocuClient  # noqa: E402

GUARDS = {"zzzProbe": 1, "private": "not-a-boolean"}
MIN_INTERVAL = 2.3  # seconds between probes; the API allows 30 requests a minute

ENDPOINTS = {
    "talk": "public-speaking",
    "workshop": "workshop",
    "content": "content-creation",
    "story": "stories",
    "interaction": "interaction-with-googlers",
    "feedback": "product-feedback-given",
    "mentoring": "mentoring",
}

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class DraftCreated(RuntimeError):
    """The API accepted a probe, which means a draft now exists."""


class UnexpectedResponse(RuntimeError):
    """The API answered something other than the 400 a probe should get."""


def split_violations(error: str) -> list[str]:
    """Split the API's validation text ("[#: a, #/x: b]") into single violations."""
    text = error.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [part.strip() for part in re.split(r",\s*(?=#)", text) if part.strip()]


def real_violations(error: str) -> list[str]:
    """The violations that are not the deliberate ones."""
    return [v for v in split_violations(error) if "zzzProbe" not in v and not v.startswith("#/private")]


class Prober:
    def __init__(self, client: AdvocuClient):
        self.client = client

    def probe(self, kind: str, payload: dict) -> list[str]:
        """Violations the API reports beyond the deliberate ones.

        Anything other than a 400 is an error, never "no violations": a 429
        (rate limit) has no validation text, and reading it as "all clear"
        would report drift that is not there.
        """
        for attempt in range(4):
            time.sleep(MIN_INTERVAL)  # stay under 30 requests a minute
            response = self.client.session.post(
                f"{BASE_URL}/activity-drafts/{ENDPOINTS[kind]}",
                json={**payload, **GUARDS},
                timeout=self.client.timeout,
            )
            if response.status_code == 429:
                time.sleep(15 * (attempt + 1))
                continue
            break
        if response.status_code < 400:
            raise DraftCreated(f"HTTP {response.status_code} on {ENDPOINTS[kind]}: {response.text}")
        if response.status_code != 400:
            raise UnexpectedResponse(f"HTTP {response.status_code} on {ENDPOINTS[kind]}: {response.text[:200]}")
        try:
            error = response.json().get("details", {}).get("error", "")
        except ValueError:
            error = ""
        if not error:
            raise UnexpectedResponse(f"HTTP 400 without validation details on {ENDPOINTS[kind]}")
        return real_violations(error)


def check_tags(prober) -> list[str]:
    bad = []
    for violation in prober.probe("talk", {"title": "Probe title", "tags": t.SUGGESTED_TAGS}):
        match = re.match(r"#/tags/(\d+):", violation)
        bad.append(t.SUGGESTED_TAGS[int(match.group(1))] if match else violation)
    return [f"tag no longer accepted: {tag}" for tag in bad]


# (kind, API field, values we believe in)
ENUMS = [
    ("content", "contentType", t.CONTENT_TYPES),
    ("feedback", "contentType", t.FEEDBACK_TYPES),
    ("workshop", "eventFormat", t.EVENT_FORMATS),
    ("talk", "eventFormat", t.EVENT_FORMATS),
    ("mentoring", "eventFormat", t.EVENT_FORMATS),
    ("interaction", "format", t.INTERACTION_FORMATS),
    ("interaction", "interactionType", t.INTERACTION_TYPES),
    ("story", "significanceType", t.SIGNIFICANCE_TYPES),
]


def check_enums(prober) -> list[str]:
    drift = []
    for kind, field, values in ENUMS:
        for value in values:
            if any(field in v for v in prober.probe(kind, {"title": "Probe title", field: value})):
                drift.append(f"{ENDPOINTS[kind]}: {field} no longer accepts {value!r}")
    return drift


def check_examples(prober) -> list[str]:
    """Every example, exactly as the CLI would send it, must pass."""
    drift = []
    for path in sorted(EXAMPLES.glob("*.*")):
        payload = t.payload_from_spec(path.stem, t.load_spec(path))
        payload.pop("private", None)  # one of the deliberate violations
        for violation in prober.probe(path.stem, payload):
            drift.append(f"{path.name}: {violation}")
    return drift


# (kind, field payload, size that must pass, size that must fail, label)
def _limits():
    return [
        ("talk", lambda n: {"title": "T" * n}, t.TITLE_MAX_LENGTH, "title"),
        ("talk", lambda n: {"description": "x" * n}, t.DESCRIPTION_MAX_LENGTH, "description"),
        ("talk", lambda n: {"additionalInfo": "x" * n}, t.ADDITIONAL_INFO_MAX_LENGTH, "additionalInfo"),
        ("feedback", lambda n: {"productDescription": "x" * n}, t.PRODUCT_DESCRIPTION_MAX_LENGTH, "productDescription"),
    ]


def check_limits(prober) -> list[str]:
    drift = []
    for kind, make, limit, field in _limits():
        base = {"title": "Probe title"}
        if prober.probe(kind, {**base, **make(limit)}):
            drift.append(f"{ENDPOINTS[kind]}: {field} no longer accepts {limit} characters")
        if not prober.probe(kind, {**base, **make(limit + 1)}):
            drift.append(f"{ENDPOINTS[kind]}: {field} now accepts more than {limit} characters")
    # Metrics: whole numbers, 1 or more.
    if prober.probe("talk", {"title": "Probe title", "metrics": {"attendees": 1}}):
        drift.append("public-speaking: attendees=1 is no longer accepted")
    if not prober.probe("talk", {"title": "Probe title", "metrics": {"attendees": 0}}):
        drift.append("public-speaking: attendees=0 is now accepted (the CLI leaves zero metrics out)")
    return drift


CHECKS = [
    ("tags", check_tags),
    ("allowed values", check_enums),
    ("examples as the CLI sends them", check_examples),
    ("limits", check_limits),
]


def main() -> int:
    prober = Prober(AdvocuClient())
    drift: list[str] = []
    try:
        for name, check in CHECKS:
            found = check(prober)
            print(f"{'DRIFT' if found else 'ok   '}  {name}")
            drift += found
    except DraftCreated as e:
        print(f"\nSTOP: a draft was created by mistake: {e}\nDelete it in the Advocu web panel.")
        return 2
    except UnexpectedResponse as e:
        print(f"\nCould not complete the check: {e}")
        return 3
    for line in drift:
        print(f"  - {line}")
    print("\nNo drift." if not drift else f"\n{len(drift)} difference(s): update templates.py and the docs.")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
