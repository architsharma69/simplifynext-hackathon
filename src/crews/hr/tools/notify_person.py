"""
crews/hr/tools/notify_person.py
CrewAI tool wrapper — write, backed by crews.hr.notify rather than
crews.hr.ledger.

The other nine tools sit on the ledger. This one does not, because sending a
message is not a ledger fact. Until the Telegram layer exists, notify.py
queues to outbox.jsonl and this tool says "queued", which is true.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/notify_person.py — only the import
of the underlying notify function changed.
"""

import json

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.notify import notify_person as _notify_person


class NotifyInput(BaseModel):
    person: str = Field(
        ..., description="Full name of the person, exactly as it appears in the roster."
    )
    message: str = Field(
        ...,
        description="The message they will read on their phone. Write it to them, "
                    "not about them: plain sentences, under 80 words, no markdown.",
    )
    urgency: str = Field(
        "normal",
        description="low, normal or high. Use high only for something that "
                    "changes what they do today.",
    )


class NotifyPerson(BaseTool):
    name: str = "notify_person"

    description: str = (
        "Queue a message to one member of the team — to tell them work has landed "
        "on them, that something moved, or to check in when their load has been "
        "high. Returns a confirmation once it is queued for delivery. "
        "Use it AFTER the ledger write it describes, never instead of one, and "
        "never to tell somebody about work that was blocked or is still waiting on "
        "the founder's confirmation. "
        "Say what changed and what you need from them. Do not pass on the "
        "founder's frustration, and do not discuss anyone else's workload."
    )
    args_schema: type[BaseModel] = NotifyInput

    def _run(self, person: str, message: str, urgency: str = "normal") -> str:
        try:
            return json.dumps(_notify_person(person, message, urgency), indent=2, default=str)
        except Exception as exc:
            return f"ERROR: {exc}"


notify_person = NotifyPerson()
tool = notify_person
