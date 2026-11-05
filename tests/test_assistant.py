"""The Assistant plugin: consent, the request to Anthropic, errors, drafts.

Runs with Hubra's fixtures once the plugin is in plugins/assistant of a
Hubra checkout (see README.md).
"""

from __future__ import annotations

import io
import json
import urllib.error
from datetime import date, timedelta

import pytest

from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

BASE = "/api/v1/app/assistant"


@pytest.fixture
def club(client, app, db, seeded_db, monkeypatch):
    """Vera may use the assistant; Max may not."""
    from hubra.core.models.event import ClubEvent
    from hubra_assistant import claude, services

    set_modules(True, "assistant")
    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    vera = _make_role_and_member(
        db, tier, name="Vera", permission_keys=["assistant.drafts.update"]
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
    monkeypatch.setattr(claude.urllib.request, "urlopen", unauthorised)
    got = client.post(f"{BASE}/drafts", json={"kind": "post", "notes": "x"})
    assert got.status_code == 502
    assert got.get_json()["message"] == "Anthropic didn't accept the API key"
    assert "sk-ant" not in got.get_data(as_text=True)
