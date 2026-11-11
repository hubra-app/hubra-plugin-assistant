"""The Assistant plugin: consent, the request to Anthropic, errors, drafts.

Runs with Hubra's fixtures once the plugin is in plugins/assistant of a
Hubra checkout (see README.md).
"""

from __future__ import annotations

import io
import json
import urllib.error
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

BASE = "/api/v1/app/assistant"


@pytest.fixture
def club(client, app, db, seeded_db, monkeypatch):
    """Vera may use the assistant and see events; Ida only the assistant;
    Max neither."""
    from hubra.core.models.event import ClubEvent
    from hubra_assistant import claude, services

    set_modules(True, "assistant")
    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    vera = _make_role_and_member(
        db,
        tier,
        name="Vera",
        permission_keys=["assistant.drafts.update", "events.read"],
    )
    ida = _make_role_and_member(
        db, tier, name="Ida", permission_keys=["assistant.drafts.update"]
    )
    max_ = _make_role_and_member(db, tier, name="Max")
    gv = ClubEvent(
        title="Generalversammlung",
        date=date.today() + timedelta(days=30),
        time="19:30",
        type="meeting",
        location="Clubhaus",
    )
    db.session.add(gv)
    db.session.commit()
    cfg = {
        "consent": False,
        "api_key": "sk-ant-secret",
        "model": "claude-opus-5-5",
        "address": "du",
        "tone": "Herzlich, kurze Sätze",
    }
    monkeypatch.setattr(services, "config", lambda: cfg)
    calls = []
    answer = {
        "stop_reason": "end_turn",
        "model": "claude-opus-5-5",
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {"title": "Einladung zur GV", "body": "Liebe Mitglieder …"}
                ),
            }
        ],
        "usage": {"input_tokens": 420, "output_tokens": 180},
    }

    def fake(body, headers):
        calls.append((body, headers))
        return answer

    real = claude._request
    monkeypatch.setattr(claude, "_request", fake)
    return {
        "real": real,
        "vera": vera.id,
        "ida": ida.id,
        "max": max_.id,
        "gv": gv.id,
        "cfg": cfg,
        "calls": calls,
        "answer": answer,
    }


def test_needs_consent_and_a_key(client, club):
    _login(client, "max@test.ch")
    assert client.get(f"{BASE}/options").status_code == 403
    _login(client, "vera@test.ch")
    opts = client.get(f"{BASE}/options").get_json()
    assert opts["ready"] is False and opts["hasKey"] and not opts["consent"]
    assert [e["title"] for e in opts["events"]] == ["Generalversammlung"]
    refused = client.post(
        f"{BASE}/drafts", json={"kind": "post", "notes": "Neue Trikots"}
    )
    assert (
        refused.status_code == 409
        and refused.get_json()["error"] == "ASSISTANT_NOT_SET_UP"
    )
    assert club["calls"] == []


def test_draft_request_and_history(client, club):
    club["cfg"]["consent"] = True
    _login(client, "vera@test.ch")
    assert (
        client.post(f"{BASE}/drafts", json={"kind": "poem", "notes": "x"}).status_code
        == 400
    )
    made = client.post(
        f"{BASE}/drafts",
        json={
            "kind": "invitation",
            "language": "de",
            "length": "short",
            "notes": "Traktanden: Jahresbericht, Wahlen",
            "eventId": club["gv"],
        },
    )
    assert made.status_code == 201
    draft = made.get_json()
    assert draft["title"] == "Einladung zur GV" and draft["tokens"] == 600

    body, headers = club["calls"][0]
    assert (
        headers["x-api-key"] == "sk-ant-secret"
        and headers["anthropic-version"] == "2026-10-21"
    )
    assert (
        headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
        and body["fallbacks"] == "default"
    )
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert (
        "«ss»" in body["system"]
        and "«du»" in body["system"]
        and "Herzlich, kurze Sätze" in body["system"]
    )
    prompt = body["messages"][0]["content"]
    assert "Generalversammlung" in prompt and "19:30" in prompt and "Clubhaus" in prompt
    assert "Traktanden: Jahresbericht, Wahlen" in prompt

    # Haiku has no server-side fallback.
    club["cfg"]["model"] = "claude-haiku-5-5"
    client.post(f"{BASE}/drafts", json={"kind": "post", "notes": "Trikots"})
    body, headers = club["calls"][1]
    assert "fallbacks" not in body and "anthropic-beta" not in headers

    mine = client.get(f"{BASE}/drafts").get_json()
    assert [d["kind"] for d in mine] == ["post", "invitation"]
    _login(client, "max@test.ch")
    assert client.delete(f"{BASE}/drafts/{draft['id']}").status_code == 403
    _login(client, "vera@test.ch")
    assert client.delete(f"{BASE}/drafts/{draft['id']}").status_code == 204


def test_errors_never_show_the_key(client, club, monkeypatch):
    from hubra_assistant import claude

    club["cfg"]["consent"] = True
    _login(client, "vera@test.ch")
    club["answer"]["stop_reason"] = "refusal"
    got = client.post(f"{BASE}/drafts", json={"kind": "post", "notes": "x"})
    assert got.status_code == 502 and "declined" in got.get_json()["message"]

    def unauthorised(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(
                b'{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}'
            ),
        )

    monkeypatch.setattr(claude, "_request", club["real"])
    monkeypatch.setattr(claude, "_opener", SimpleNamespace(open=unauthorised))
    got = client.post(f"{BASE}/drafts", json={"kind": "post", "notes": "x"})
    assert got.status_code == 502
    assert got.get_json()["message"] == "Anthropic didn't accept the API key"
    assert "sk-ant" not in got.get_data(as_text=True)


def test_events_need_the_events_right(client, club):
    """The assistant right alone doesn't open the club's calendar."""
    club["cfg"]["consent"] = True
    _login(client, "ida@test.ch")
    opts = client.get(f"{BASE}/options").get_json()
    assert opts["events"] == []
    got = client.post(
        f"{BASE}/drafts",
        json={"kind": "invitation", "notes": "GV", "eventId": club["gv"]},
    )
    assert got.status_code == 403 and club["calls"] == []
    assert (
        client.post(f"{BASE}/drafts", json={"kind": "post", "notes": "x"}).status_code
        == 201
    )


def test_cancelled_events_are_not_offered(client, club, db):
    from datetime import UTC, datetime

    from hubra.core.models.event import ClubEvent

    db.session.get(ClubEvent, club["gv"]).cancelled_at = datetime.now(UTC)
    db.session.commit()
    _login(client, "vera@test.ch")
    assert client.get(f"{BASE}/options").get_json()["events"] == []


@pytest.mark.parametrize("key", ["kind", "language", "length"])
def test_choices_must_be_text(client, club, key):
    club["cfg"]["consent"] = True
    _login(client, "vera@test.ch")
    got = client.post(f"{BASE}/drafts", json={key: ["post"], "notes": "x"})
    assert got.status_code == 400 and club["calls"] == []


@pytest.mark.parametrize(
    "answer",
    [
        {"stop_reason": "end_turn", "content": "nope"},
        {"stop_reason": "end_turn", "content": [1, {"type": "text", "text": "[]"}]},
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "42"}]},
    ],
)
def test_odd_answers_are_a_502_not_a_crash(client, club, monkeypatch, answer):
    from hubra_assistant import claude

    club["cfg"]["consent"] = True
    _login(client, "vera@test.ch")
    monkeypatch.setattr(claude, "_request", lambda body, headers: answer)
    got = client.post(f"{BASE}/drafts", json={"kind": "post", "notes": "x"})
    assert got.status_code == 502 and "wasn't a draft" in got.get_json()["message"]


def test_odd_usage_counts_as_zero(client, club):
    club["cfg"]["consent"] = True
    club["answer"]["usage"] = {"input_tokens": "lots", "output_tokens": None}
    _login(client, "vera@test.ch")
    got = client.post(f"{BASE}/drafts", json={"kind": "post", "notes": "x"})
    assert got.status_code == 201 and got.get_json()["tokens"] == 0


def test_a_redirect_is_not_followed_with_the_key():
    """urllib would resend x-api-key to wherever a redirect points."""
    import urllib.request

    from hubra_assistant import claude

    handler = next(
        h
        for h in claude._opener.handlers
        if isinstance(h, urllib.request.HTTPRedirectHandler)
    )
    req = urllib.request.Request(claude.URL, headers={"x-api-key": "sk-ant-secret"})
    assert (
        handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/")
        is None
    )
