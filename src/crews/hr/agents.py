"""
crews/hr/agents.py
Agent definition for the HR / Workload Manager specialist. Mirrors
crews/document/agents.py's pattern (a plain CrewAI Agent built from
Config-driven model settings) — but there's only one agent here, not a team
of specialists, so there's no "team lead" routing step: hr_manager_agent
handles a rephrased HR request end to end.

The team roster and current workload are injected directly into its prompt
(crews/hr/tasks.py, built from crews/hr/roster.py's snapshot of
knowledge/hr/team_roster.json) the same way crews/document injects its
knowledge-base JSON, so there are no read tools here any more — only the
safety guardrail and the (stateless — see crews/hr/README.md) write-shaped
tools remain.

Ported from the standalone workload_manager prototype's
agents/hr_manager.jsonc (role/goal/backstory/tool list/settings), rebuilt as
a Python crewai.Agent instead of a JSONC crew definition so it plugs directly
into OrchestratorFlow the same way every other specialist does.
"""
from __future__ import annotations

from crewai import Agent, LLM

from Config import config
from crews.hr.tools.check_assignment_safety import check_assignment_safety
from crews.hr.tools.create_task import create_task
from crews.hr.tools.assign_task import assign_task
from crews.hr.tools.update_task_status import update_task_status
from crews.hr.tools.log_wellbeing_event import log_wellbeing_event
from crews.hr.tools.notify_person import notify_person

# Single LLM config for the HR agent; HR_TEAM_MODEL / HR_TEAM_API_KEY in
# Config/config.py control model/provider and credentials, same pattern as
# DOCUMENT_TEAM_MODEL for the document team. Defaults to the same
# openai/gpt-4o-mini every other crew in this repo defaults to rather than
# the original prototype's bedrock/* config, since no Bedrock credentials
# are wired up yet — see crews/hr/README.md.
llm = LLM(
    model=config.HR_TEAM_MODEL
)

hr_manager_agent = Agent(
    role="Chief of Staff for a small startup team",
    goal=(
        "Keep every person's real workload visible, place new work with "
        "whoever has the capacity and the skill for it, and make sure nobody "
        "is quietly carrying more than they can hold."
    ),
    backstory=(
        "You spent six years as the operations lead at three seed-stage "
        "startups. Twice you watched a good engineer quietly absorb "
        "everyone else's overflow until they burned out and left — and both "
        "times the founder was genuinely surprised, even though the load "
        "had been sitting in the data for weeks with nobody reading it.\n\n"
        "So now you count. You are the only person here whose job is to "
        "know what each person is actually carrying, and you trust the "
        "numbers in front of you over anyone's optimism, including the "
        "founder's.\n\n"
        "You are warm with the team and blunt with the founder. When you "
        "place work you say who, why, and what trade-off you made. When "
        "placing it would hurt someone, you say no and offer the next best "
        "option — you would rather be argued with than be the reason "
        "somebody leaves.\n\n"
        "You never speculate about a person's performance, attitude, or "
        "worth. You talk about hours, skills and dates, because those are "
        "the only things you actually know."
    ),
    tools=[
        check_assignment_safety,
        create_task,
        assign_task,
        update_task_status,
        log_wellbeing_event,
        notify_person,
    ],
    llm=llm,
    verbose=True,
    allow_delegation=False,
    # No agent-level "guardrail" here on purpose (mirrors the original
    # hr_manager.jsonc) — that option is checked by an LLM, which means it
    # can be talked around. The real guardrail is check_assignment_safety(),
    # plain Python that assign_task refuses to run without.
    max_iter=12,
    max_rpm=20,
    max_execution_time=60,
    max_retry_limit=2,
    # Conversation history comes from OrchestratorState/session store, not
    # CrewAI memory — two memory systems that disagree is a bad time.
    memory=False,
    # Tool responses are just arithmetic over a static fixture now (see
    # crews/hr/roster.py), so there's no real staleness risk left — kept
    # off anyway since it costs nothing here.
    cache=False,
    respect_context_window=True,
)
