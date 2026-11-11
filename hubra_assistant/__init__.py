"""Assistant: drafts for the board, written by Claude (Anthropic).

The board picks what it needs (a post, an invitation, a reminder, a summary
of minutes, or anything else), writes a few notes and gets a draft in the
club's tone and language to copy and change. Nothing is sent to Anthropic
until the club enters its own API key and agrees, in the module's settings,
that the notes it writes go there. Hubra sends only what the person typed
and, if they pick one, the event's title, date and place; never member
lists or other data. Members' names, mail addresses, phone numbers and IBANs
in it are swapped for placeholders first (privacy.py). Drafts are deleted
after ``keep_days`` by a daily job, and right away once their author is
no longer a member.

Permission:
    assistant.drafts.update   write drafts with the assistant
"""

from hubra.core.modules import Blueprint, Module, NavItem, Schedule, SettingField

module = Module(
    code="assistant",
    name="Assistant",
    description="Drafts for the board, written by Claude",
    default_enabled=False,
    depends_on=("members",),
    blueprints=(
        Blueprint("hubra_assistant.routes", "assistant_bp", "/api/v1/app/assistant"),
    ),
    nav=(
        NavItem(
            "/app/assistant",
            "shell.nav.assistant",
            "sparkles",
            section="more",
            order=35,
            perms=("assistant.drafts.update",),
        ),
    ),
    settings=(
        SettingField(
            "consent",
            "bool",
            default=False,
            label="Send our notes to Anthropic",
            description=(
                "We agree that what board members type into the assistant is sent "
                "to Anthropic (USA) to write the draft. Off: the assistant does nothing."
            ),
        ),
        SettingField(
            "api_key",
            "secret",
            label="Anthropic API key",
            description="The club's own key from console.anthropic.com; the club pays for its use",
        ),
        SettingField(
            "model",
            "choice",
            default="claude-opus-5-5",
            choices=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"),
            label="Model",
            description="Opus writes best; Sonnet and Haiku cost less",
        ),
        SettingField(
            "address",
            "choice",
            default="du",
            choices=("du", "sie"),
            label="How the club addresses members",
        ),
        SettingField(
            "tone",
            "str",
            label="The club's tone",
            description="A sentence or two, e.g. «Herzlich und locker, kurze Sätze, Schweizer Rechtschreibung (ss)»",
        ),
        SettingField(
            "keep_days",
            "int",
            default=90,
            label="Keep drafts for (days)",
            description="Drafts, with the notes and minutes they were written from, are deleted after this many days (1 to 3650)",
        ),
        SettingField(
            "club_per_day",
            "int",
            default=100,
            label="Drafts per day for the whole club",
            description="Caps what the API key is used for in a day, across all board members; 0 means no cap",
        ),
    ),
    tasks=("hubra_assistant.tasks",),
    schedule=(Schedule("assistant-purge", "hubra_assistant.tasks.purge", 86400.0),),
    tables=("assistant_drafts",),
)
