# Assistant

## 1.0.2

Security fixes from the plugin audit:

- The upcoming events (and picking one for a draft) need the right to view
  events too; the assistant right alone no longer lists the club's calendar.
  Cancelled events aren't offered.
- The request to Anthropic doesn't follow redirects, so the club's API key
  can't be resent to another host.
- A `kind`, `language` or `length` that isn't text, or an answer from
  Anthropic in an unexpected shape, gives a clear error instead of a 500.

## 1.0.1

The Einstellungen button on the Assistant page opens the plugin's own
settings form (consent, API key), not the whole module list. Needs Hubra
with `/app/settings/modules?module=<code>` (newer than 0.2.4); older versions
show the module list as before.

## 1.0.0

First version: drafts of posts, invitations, reminders and minutes summaries
with Claude, in the club's language, form of address and tone; the club's own
Anthropic API key and an explicit consent switch; the last drafts per person.
