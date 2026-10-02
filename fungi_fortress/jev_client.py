"""HTTP client for one Jev evaluation.

Uses the TypeSafe System One endpoint directly. The published SDK is not
imported: it is new, and this project still runs on interpreters where adding
it would mean taking an unreviewed wheel.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

SYSTEMONE_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"


class JevError(RuntimeError):
    """The evaluation endpoint refused the call or returned an unusable body."""


def evaluate(
    state: Any,
    questions: dict[str, Any],
    api_key: str,
    timeout: float = 2.5,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """POST one state and its questions. Returns the parsed JSON body.

    `opener` is the urllib-compatible callable tests use instead of the network.
    """
    if not api_key:
        raise JevError("TYPESAFE_API_KEY is not set")
    if not questions:
        raise JevError("Jev call has no questions")

    payload = {"state": state, "model": JEV_MODEL, "questions": questions}
    raw = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        SYSTEMONE_URL,
        data=raw,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    open_call = opener or urllib.request.urlopen
    try:
        with open_call(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise JevError(f"Jev HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise JevError(f"Jev request failed: {exc.reason}") from exc

    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise JevError("Jev returned non-JSON") from exc
    if not isinstance(parsed, dict) or "answers" not in parsed:
        raise JevError("Jev response has no answers")
    return parsed
