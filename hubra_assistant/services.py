"""What the assistant is asked: the club's voice and the board's notes."""

from __future__ import annotations

from datetime import datetime, timezone

KINDS = ("post", "invitation", "reminder", "minutes", "other")
LANGUAGES = {
    "de": "German as written in Switzerland (use «ss», never «ß»)",
    "fr": "French as written in Switzerland",
    "it": "Italian as written in Switzerland",
    "en": "British English",
}
LENGTHS = {
    "short": "short: a few sentences",
    "medium": "medium: three to five short paragraphs",
    "long": "long: as long as the content needs",
}
NOTES_LIMIT = 4000
MINUTES_LIMIT = 60000
PER_HOUR = 30
KEEP_DAYS = 90
CLUB_PER_DAY = 100
# Picking an event (and seeing the upcoming ones) needs the events right too.
EVENTS_READ = "events.read"

TASKS = {
    "post": "Write a news post for the club's members, to appear in the club app.",
    "invitation": (
        "Write an invitation (for example to the general meeting or a club event). "
        "Give date, time and place clearly near the top, list the agenda if the notes "
        "have one, and say how and by when to sign up if the notes say so."
    ),
    "reminder": (
        "Write a friendly reminder (for example an unpaid membership fee or a sign-up "
        "deadline). Stay polite and clear about what to do and by when."
    ),
    "minutes": (
        "Summarise these minutes for the members who weren't there: the decisions, "
        "what happens next and who does it. Leave out discussion details and anything "
        "personal that isn't a decision."
    ),
    "other": "Write the text the notes ask for.",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def config() -> dict:
    from hubra.core.modules import get_config

    return get_config("assistant")


def _setting(cfg: dict, key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(cfg.get(key) if cfg.get(key) is not None else default)
    except (TypeError, ValueError):
        value = default
    return min(max(value, low), high)


def keep_days(cfg: dict) -> int:
    return _setting(cfg, "keep_days", KEEP_DAYS, 1, 3650)


def club_per_day(cfg: dict) -> int:
    """0: no cap."""
    return _setting(cfg, "club_per_day", CLUB_PER_DAY, 0, 100000)


def made_since(span, member_id: int | None = None) -> int:
    """Drafts written in the last *span* (by one member, or the whole club),
    from the audit log: a deleted draft still counts."""
    from sqlalchemy import func, select

    from hubra.core.extensions import db
    from hubra.core.models.audit import AuditEntry

    query = (
        select(func.count(AuditEntry.id))
        .where(AuditEntry.action == "assistant.draft")
        .where(AuditEntry.time >= now() - span)
    )
    if member_id is not None:
        query = query.where(AuditEntry.actor_id == member_id)
    return int(db.session.scalar(query) or 0)


def purge(cfg: dict) -> int:
    """Delete drafts older than keep_days and those whose author is gone.

    Club schemas carry no foreign keys (they're cloned with LIKE … INCLUDING
    ALL), so ON DELETE SET NULL never runs: a deleted member's id stays in
    created_by. Both cases are removed here.
    """
    from datetime import timedelta

    from sqlalchemy import delete, exists, or_, select

    from hubra.core.extensions import db
    from hubra.core.models.member import Member

    from .models import AssistantDraft

    gone = ~exists(select(Member.id).where(Member.id == AssistantDraft.created_by))
    result = db.session.execute(
        delete(AssistantDraft)
        .where(
            or_(
                AssistantDraft.created_at < now() - timedelta(days=keep_days(cfg)),
                AssistantDraft.created_by.is_(None),
                gone,
            )
        )
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)


def ready(cfg: dict) -> bool:
    return bool(cfg.get("consent")) and bool(str(cfg.get("api_key") or "").strip())


def club_name() -> str:
    from hubra.core.services.email import club_display_name

    try:
        return club_display_name() or "the club"
    except Exception:  # noqa: BLE001 - a missing name doesn't stop a draft
        return "the club"


def system_prompt(cfg: dict, language: str, length: str) -> str:
    address = (
        "the polite «Sie»"
        if cfg.get("address") == "sie"
        else "the informal «du» (plural «ihr»)"
    )
    tone = str(cfg.get("tone") or "").strip()
    lines = [
        f"You write texts for the board of {club_name()}, a Swiss club (Verein).",
        f"Write in {LANGUAGES.get(language, LANGUAGES['de'])}.",
        f"Address members with {address} where the language has the distinction.",
        f"Length: {LENGTHS.get(length, LENGTHS['medium'])}.",
        "Use only facts from the notes and the event details; where something needed is "
        "missing, put a clear placeholder in square brackets, e.g. [Datum], instead of inventing it.",
        "Plain text only: no Markdown headings, no bullet symbols other than «-», no emojis "
        "unless the club's tone asks for them. Separate paragraphs with an empty line.",
        "Sign off as the board (Vorstand) unless the notes name someone.",
        "Return the title or subject line in «title» and the text in «body».",
        (
            "Placeholders like [Person 1], [E-Mail 1], [Telefon 1] or [IBAN 1] stand "
            "for personal data that Hubra fills in afterwards: keep each exactly as "
            "written, never translate, inflect or change it, and don't guess what is "
            "behind it."
        ),
    ]
    if tone:
        lines.append(f"The club's tone, in its own words: {tone}")
    return "\n".join(lines)


def user_prompt(kind: str, notes: str, event=None, mask=None) -> str:
    mask = mask or (lambda text: text)
    parts = [TASKS.get(kind, TASKS["other"])]
    if event is not None:
        when = f"{event.date:%d.%m.%Y}"
        if event.end_date and event.end_date != event.date:
            when += f" – {event.end_date:%d.%m.%Y}"
        if event.time and not event.all_day:
            when += f", {event.time}"
        details = [f"Title: {mask(event.title)}", f"Date: {when}"]
        if event.location:
            details.append(f"Place: {mask(event.location)}")
        parts.append("<event>\n" + "\n".join(details) + "\n</event>")
    tag = "minutes" if kind == "minutes" else "notes"
    parts.append(f"<{tag}>\n{mask(notes)}\n</{tag}>")
    return "\n\n".join(parts)
