# Assistant

## 1.1.0

Needs Hubra 0.2.3 or newer (for the daily job).

Privacy and security from the plugin audit:

- Members' names, mail addresses, phone numbers and IBANs are replaced with
  placeholders like [Person 1] before anything goes to Anthropic, and put
  back into the draft.
- Drafts are deleted after 90 days (new setting **Keep drafts for (days)**)
  by a daily job, and when their author is no longer a member (club schemas
  have no foreign keys, so the old ON DELETE SET NULL never ran).
- New setting **Drafts per day for the whole club** (100; 0 = no cap). The
  hourly and daily limits count from the audit log, so deleting drafts
  doesn't free up more.
- Deleting a draft is recorded in the audit log.

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
