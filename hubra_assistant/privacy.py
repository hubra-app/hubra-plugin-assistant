"""Personal data stays in Hubra: names, mail addresses, phone numbers and
IBANs in what goes to Anthropic are swapped for placeholders like
[Person 1] or [E-Mail 1], and put back into the draft that comes back.

Names are the club's members' (full name, and a first or last name alone
when only one member has it). Matching is exact and case-sensitive on whole
words, so it finds what the board typed as it is spelled in Hubra; a name
spelled differently or a non-member's name goes as typed. The board sees
this in the note under the form.
"""

from __future__ import annotations

import re
from collections import Counter

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# CH/LI IBANs and other European ones, with or without spaces.
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")
# +41 79 123 45 67, 079 123 45 67, 0041791234567, +49 30 1234567 …
PHONE = re.compile(r"(?<![\w+])(?:\+|00)?\d(?:[ ./-]?\d){8,13}(?!\w)")
MIN_NAME = 3


def _members() -> list[tuple[str, str]]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from hubra.core.extensions import db
    from hubra.core.models.member import Member

    rows = db.session.scalars(select(Member).options(selectinload(Member.user)))
    out = []
    for m in rows:
        first = (m.first_name or "").strip()
        last = (m.last_name or "").strip()
        if first or last:
            out.append((first, last))
    return out


def _name_terms(members: list[tuple[str, str]]) -> list[str]:
    """Full names first, then first or last names only one member has."""
    terms: set[str] = set()
    for first, last in members:
        if first and last:
            terms.add(f"{first} {last}")
            terms.add(f"{last} {first}")
    firsts = Counter(f for f, _ in members if f)
    lasts = Counter(la for _, la in members if la)
    for counts in (firsts, lasts):
        for word, n in counts.items():
            if n == 1 and len(word) >= MIN_NAME:
                terms.add(word)
    return sorted(terms, key=len, reverse=True)


class Masker:
    """Swaps personal data for placeholders and back, one per request."""

    def __init__(self, members: list[tuple[str, str]] | None = None):
        terms = _name_terms(_members() if members is None else members)
        self._names = (
            re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, terms)) + r")(?!\w)")
            if terms
            else None
        )
        self._by_value: dict[tuple[str, str], str] = {}
        self._by_token: dict[str, str] = {}
        self._counts: Counter[str] = Counter()

    def _token(self, label: str, value: str) -> str:
        key = (label, value)
        if key not in self._by_value:
            self._counts[label] += 1
            token = f"[{label} {self._counts[label]}]"
            self._by_value[key] = token
            self._by_token[token] = value
        return self._by_value[key]

    def mask(self, text: str | None) -> str | None:
        if not text:
            return text
        text = EMAIL.sub(lambda m: self._token("E-Mail", m.group()), text)
        text = IBAN.sub(lambda m: self._token("IBAN", m.group()), text)
        text = PHONE.sub(lambda m: self._token("Telefon", m.group()), text)
        if self._names is not None:
            text = self._names.sub(lambda m: self._token("Person", m.group()), text)
        return text

    def unmask(self, text: str) -> str:
        if not text or not self._by_token:
            return text
        pattern = "|".join(
            map(re.escape, sorted(self._by_token, key=len, reverse=True))
        )
        return re.sub(pattern, lambda m: self._by_token[m.group()], text)

    @property
    def masked(self) -> int:
        return len(self._by_token)
