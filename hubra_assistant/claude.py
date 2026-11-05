"""One call to Anthropic's Messages API (https://docs.claude.com).

Plugins can't bring their own Python packages, so this speaks plain HTTPS
to the documented endpoint instead of using the anthropic SDK. The answer
is constrained to JSON ({title, body}) with structured outputs; a decline
by Anthropic's safety classifiers is re-run on Anthropic's recommended
fallback model (fallbacks: "default") where the model supports it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
WITH_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5"}
MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
TIMEOUT = 120

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Title or subject line"},
        "body": {
            "type": "string",
            "description": "The text, paragraphs separated by an empty line",
        },
    },
    "required": ["title", "body"],
    "additionalProperties": False,
}


class ClaudeError(Exception):
    """Shown to the board, so it never carries the key."""


@dataclass
class Draft:
    title: str
    body: str
    model: str
    input_tokens: int
    output_tokens: int


def _request(body: dict, headers: dict) -> dict:
    """One call; tests replace this."""
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(), method="POST", headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        try:
            err = json.loads(exc.read() or b"{}").get("error") or {}
        except (ValueError, AttributeError):
            err = {}
        kind = str(err.get("type") or "")
        if code == 401 or kind == "authentication_error":
            raise ClaudeError("Anthropic didn't accept the API key") from None
        if code == 429 or kind == "rate_limit_error":
            raise ClaudeError(
                "Anthropic is busy or the key's limit is reached; try again in a minute"
            ) from None
        if code == 400 and "credit" in str(err.get("message") or "").lower():
            raise ClaudeError("The Anthropic account has no credit left") from None
        if code >= 500 or kind == "overloaded_error":
            raise ClaudeError(
                "Anthropic is not available right now; try again later"
            ) from None
        raise ClaudeError(f"Anthropic answered HTTP {code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ClaudeError("Anthropic can't be reached") from None
    except ValueError:
        raise ClaudeError("Anthropic sent an answer Hubra can't read") from None


def draft(api_key: str, model: str, system: str, prompt: str) -> Draft:
    model = model if model in MODELS else MODELS[0]
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": API_VERSION,
    }
    body: dict = {
        "model": model,
        "max_tokens": 16000,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {
            "effort": "medium",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
    }
    if model in WITH_FALLBACK:
        headers["anthropic-beta"] = FALLBACK_BETA
        body["fallbacks"] = "default"
    got = _request(body, headers)
    stop = got.get("stop_reason")
    if stop == "refusal":
        raise ClaudeError("Claude declined to write this; rephrase the notes")
    if stop == "max_tokens":
        raise ClaudeError("The draft got too long; ask for a shorter text")
    text = "".join(
        b.get("text", "") for b in got.get("content") or [] if b.get("type") == "text"
    )
    try:
        data = json.loads(text)
    except ValueError:
        raise ClaudeError("Claude's answer wasn't a draft; try again") from None
    usage = got.get("usage") or {}
    return Draft(
        title=str(data.get("title") or "").strip(),
        body=str(data.get("body") or "").strip(),
        model=str(got.get("model") or model),
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
    )
