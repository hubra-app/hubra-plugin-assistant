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
    ]
    if tone:
        lines.append(f"The club's tone, in its own words: {tone}")
    return "\n".join(lines)


def user_prompt(kind: str, notes: str, event=None) -> str:
    parts = [TASKS.get(kind, TASKS["other"])]
    if event is not None:
        when = f"{event.date:%d.%m.%Y}"
        if event.end_date and event.end_date != event.date:
            when += f" – {event.end_date:%d.%m.%Y}"
        if event.time and not event.all_day:
            when += f", {event.time}"
        details = [f"Title: {event.title}", f"Date: {when}"]
        if event.location:
            details.append(f"Place: {event.location}")
        parts.append("<event>\n" + "\n".join(details) + "\n</event>")
    tag = "minutes" if kind == "minutes" else "notes"
    parts.append(f"<{tag}>\n{notes}\n</{tag}>")
    return "\n\n".join(parts)
