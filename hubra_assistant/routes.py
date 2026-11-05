"""Assistant API: /api/v1/app/assistant (all of it needs assistant.drafts.update).

GET    /options          whether it is ready, the club's settings, upcoming events
GET    /drafts           the caller's last drafts
POST   /drafts           {kind, language, length, notes, eventId?}: a new draft
DELETE /drafts/<id>      one of the caller's drafts
"""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, jsonify
from sqlalchemy import func, select

from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.permissions import permission_required
from hubra.core.utils import log_audit

from . import claude, services
from .body import Invalid, _body, _int, _iso, _text
from .models import AssistantDraft

assistant_bp = Blueprint("assistant_bp", __name__)

LABEL = "Write drafts with the AI assistant"


@assistant_bp.errorhandler(Invalid)
def _invalid(exc: Invalid):
    return api_error("VALIDATION_ERROR", exc.message, 400)


def _draft(d: AssistantDraft) -> dict:
    return {
        "id": d.id,
        "kind": d.kind,
        "language": d.language,
        "notes": d.notes,
        "eventId": d.event_id,
        "title": d.title,
        "body": d.body,
        "model": d.model,
        "tokens": d.input_tokens + d.output_tokens,
        "createdAt": _iso(d.created_at),
    }


@assistant_bp.get("/options")
@permission_required("drafts", "update", LABEL)
def options():
    from hubra.core.models.event import ClubEvent

    cfg = services.config()
    today = date.today()
    events = db.session.scalars(
        select(ClubEvent)
        .where(ClubEvent.date >= today)
        .where(ClubEvent.date <= today + timedelta(days=180))
        .order_by(ClubEvent.date)
        .limit(60)
    )
    return jsonify(
        {
            "ready": services.ready(cfg),
            "consent": bool(cfg.get("consent")),
            "hasKey": bool(str(cfg.get("api_key") or "").strip()),
            "model": cfg.get("model") or claude.MODELS[0],
            "address": cfg.get("address") or "du",
            "tone": cfg.get("tone") or "",
            "events": [
                {"id": e.id, "title": e.title, "date": e.date.isoformat()}
                for e in events
            ],
        }
    )


@assistant_bp.get("/drafts")
@permission_required("drafts", "update", LABEL)
def list_drafts():
    member = get_current_member()
    rows = db.session.scalars(
        select(AssistantDraft)
        .where(AssistantDraft.created_by == member.id)
        .order_by(AssistantDraft.id.desc())
        .limit(30)
    )
    return jsonify([_draft(d) for d in rows])


@assistant_bp.post("/drafts")
@permission_required("drafts", "update", LABEL)
def create_draft():
    from hubra.core.models.event import ClubEvent

    member = get_current_member()
    data = _body()
    kind = data.get("kind") or "post"
    if kind not in services.KINDS:
        raise Invalid("kind must be one of " + ", ".join(services.KINDS))
    language = data.get("language") or "de"
    if language not in services.LANGUAGES:
        raise Invalid("language must be one of " + ", ".join(services.LANGUAGES))
    length = data.get("length") or "medium"
    if length not in services.LENGTHS:
        raise Invalid("length must be short, medium or long")
    limit = services.MINUTES_LIMIT if kind == "minutes" else services.NOTES_LIMIT
    notes = _text(data, "notes", limit, required=True)
    event = None
    event_id = _int(data, "eventId", 1, 2**31 - 1)
    if event_id:
        event = db.session.get(ClubEvent, event_id)
        if event is None:
            raise Invalid("eventId must be an event")

    cfg = services.config()
    if not services.ready(cfg):
        return api_error(
            "ASSISTANT_NOT_SET_UP",
            "The club hasn't agreed to send notes to Anthropic or entered its API key yet.",
            409,
        )
    recent = db.session.scalar(
        select(func.count(AssistantDraft.id))
        .where(AssistantDraft.created_by == member.id)
        .where(AssistantDraft.created_at >= services.now() - timedelta(hours=1))
    )
    if (recent or 0) >= services.PER_HOUR:
        return api_error(
            "TOO_MANY_DRAFTS",
            "That's enough drafts for this hour; try again later.",
            429,
        )

    try:
        got = claude.draft(
            str(cfg["api_key"]).strip(),
            str(cfg.get("model") or claude.MODELS[0]),
            services.system_prompt(cfg, language, length),
            services.user_prompt(kind, notes, event),
        )
    except claude.ClaudeError as exc:
        return api_error("ASSISTANT_FAILED", str(exc), 502)

    row = AssistantDraft(
        kind=kind,
        language=language,
        notes=notes,
        event_id=event.id if event else None,
        title=got.title[:300],
        body=got.body,
        model=got.model[:40],
        input_tokens=got.input_tokens,
        output_tokens=got.output_tokens,
        created_by=member.id,
        created_at=services.now(),
    )
    db.session.add(row)
    db.session.flush()
    log_audit(member.id, "assistant.draft", "AssistantDraft", row.id, kind)
    db.session.commit()
    return jsonify(_draft(row)), 201


@assistant_bp.delete("/drafts/<int:draft_id>")
@permission_required("drafts", "update", LABEL)
def delete_draft(draft_id: int):
    member = get_current_member()
    row = db.session.get(AssistantDraft, draft_id)
    if row is None or row.created_by != member.id:
        return api_error("NOT_FOUND", "not found", 404)
    db.session.delete(row)
    db.session.commit()
    return "", 204
