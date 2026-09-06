"""
crews/hr/notify.py
Outbound messages to the team.

There is no ledger function for this because notifying somebody is not a
ledger fact — it is an outbound side effect. The transport (Telegram, Slack,
email) does not exist yet, so this module does the two parts that ARE
knowable today:

  1. resolve a name to a contact handle from the people table
  2. append the message to an outbox file the delivery layer drains

That keeps the agent honest. It can say "queued for @priya" and that is
literally true, instead of claiming a message was sent by a bot nobody
has written.

When the Telegram layer lands, replace `_deliver` and leave the rest alone.

Ported from plan/workload_manager/notify.py — only the import of the name
lookup changed (`crews.hr.ledger` -> `crews.hr.roster`, since the ledger
is gone; see crews/hr/roster.py).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from crews.hr.roster import RosterError, get_person, get_team_roster

OUTBOX_PATH = Path(__file__).resolve().parent / "outbox.jsonl"

MAX_CHARS = 1000


def _deliver(entry: dict) -> str:
    """The only part that changes when a real transport arrives.

    Today: append to outbox.jsonl. The Flow (or a cron) reads this file,
    sends what it finds, and truncates it.
    """
    with OUTBOX_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return "queued"


def notify_person(person: str, message: str, urgency: str = "normal") -> dict:
    """Queue a message for one person. Returns a quotable confirmation."""
    valid_urgency = ("low", "normal", "high")
    if urgency not in valid_urgency:
        raise RosterError(
            f"'{urgency}' is not an urgency. Use one of: {', '.join(valid_urgency)}."
        )

    who = get_person(person)
    if not who:
        names = ", ".join(p["name"] for p in get_team_roster())
        raise RosterError(f"No one named '{person}' is in the roster. The team is: {names}.")

    text = (message or "").strip()
    if not text:
        raise RosterError("A notification needs a message.")
    if len(text) > MAX_CHARS:
        raise RosterError(
            f"That message is {len(text)} characters. Keep it under {MAX_CHARS} — "
            "these land on a phone."
        )

    handle = who["contact_handle"] or ""
    entry = {
        "person": who["name"],
        "handle": handle,
        "urgency": urgency,
        "message": text,
        "queued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    state = _deliver(entry)

    where = handle if handle else "no contact handle on file"
    return {
        "person": who["name"],
        "handle": handle,
        "urgency": urgency,
        "state": state,
        "confirmation": f"Message to {who['name']} ({where}) {state} for delivery.",
    }


def read_outbox() -> list[dict]:
    """Everything queued and not yet drained. Used by tests and the Flow."""
    if not OUTBOX_PATH.exists():
        return []
    with OUTBOX_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def drain_outbox() -> list[dict]:
    """Return everything queued, then clear the file."""
    entries = read_outbox()
    OUTBOX_PATH.write_text("", encoding="utf-8")
    return entries
