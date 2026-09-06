# HR crew — workload manager

Implements the "HR agent (workload manager, keeps track of employees and
rosters)" piece of the larger BRO system: the `hr` specialist that
`flows/orchestrator_flow.py`'s `OrchestratorFlow` routes to.

This is a port of a standalone CrewAI prototype (`plan/workload_manager/` —
JSON-config crew + SQLite ledger + Python safety guardrail, built and unit
tested independently) into this repo's Python-agent convention, so it plugs
into `OrchestratorFlow` the same way `crews/document` does.

## Layout

```
src/crews/hr/
  agents.py        hr_manager_agent — one standalone CrewAI Agent, ten tools,
                    no team-lead routing step (there's only one HR agent).
  tasks.py          build_hr_prompt(sub_query, today) — the ordered procedure
                     prompt, ported verbatim from the prototype's crew.jsonc.
  schemas.py        WorkloadResponse and friends (Allocation, TeamStatus, ...) —
                     the typed contract hr_manager_agent returns.
  db.py             SQLite schema (people, tasks, workload_log,
                     wellbeing_events) + ISO-week date helpers.
  ledger.py         Eight ledger functions (four read, four write). Pure
                     Python, unit-testable with no API key and no model.
  safety.py         check_assignment_safety() — the actual guardrail.
                     Deterministic OK/WARN/BLOCK: 85% load warns, 100%
                     blocks, 3 consecutive overloaded weeks blocks.
  notify.py         notify_person() — queues to outbox.jsonl. No delivery
                     transport (Telegram/Slack) exists yet; see below.
  seed.py           Builds workload.db with 8 people and 14 tasks (Priya
                     deliberately overloaded). Run once per machine — see
                     "Setup" below.
  workload.db       Local SQLite ledger. Gitignored, NOT checked in: seed.py
                     lays the tasks out relative to today's date, so a
                     committed copy silently goes stale the moment the week
                     rolls over.
  tools/            Ten thin BaseTool wrappers, one per ledger/safety/notify
                     function — see "Why BaseTool, not @tool" below.
```

## How it's actually invoked

Same pattern as the document crew, but simpler (one agent, not a team lead
plus specialists):

1. `OrchestratorFlow.route_hr()` fires when the top-level Orchestrator picked
   `"hr"` as a specialist for this turn.
2. It calls `self._run_hr_team(sub_query)`, which builds the procedure prompt
   (`tasks.build_hr_prompt`) with today's date, and calls
   `hr_manager_agent.kickoff(prompt, response_format=WorkloadResponse)`.
3. `hr_manager_agent` works the procedure using its ten tools — reading the
   ledger before answering, and always calling `check_assignment_safety`
   before `assign_task`, exactly as the prompt instructs.
4. The structured `WorkloadResponse.message` (falling back to the raw text if
   structured parsing fails) is what lands in
   `OrchestratorState.active_agent_outputs["hr"]` for the final synthesis
   step — the founder-readable sentence, not the whole JSON object.

## The safety guardrail

`ledger.assign_task` raises unless it is handed a `safety_verdict` that came
from `check_assignment_safety`, and refuses outright on `BLOCK` — this is
enforced in plain Python, not in the prompt, so it can't be talked around by
the model. `tools/assign_task.py`'s wrapper adds one thing on top: when the
ledger refuses, it calls `safety.suggest_alternatives` and appends who
*would* pass, so a refusal always comes with an option instead of a dead end.

## Why BaseTool, not `@tool`

`crews/document/tools/*.py` use CrewAI's `@tool(...)` decorator. These ten
use class-based `BaseTool` subclasses instead — both are valid CrewAI tool
patterns, and this crew keeps the prototype's original style rather than
rewriting it, because the exact `_run` error-handling behavior (catch every
exception, return `"ERROR: ..."` as text — a *raised* exception kills the
whole agent run) was already built and unit-proof in the prototype. Each
crew in this repo is self-contained (`crews/README.md`), so the two styles
coexisting across `document/` and `hr/` is expected, not an inconsistency to
fix.

## Model config

`Config/config.py` adds `HR_TEAM_MODEL` / `HR_TEAM_API_KEY`, mirroring
`DOCUMENT_TEAM_MODEL`. **This defaults to `openai/gpt-4o-mini`**, not the
prototype's original `bedrock/us-gov-east-1/...` — the prototype's build
notes recorded that no AWS Bedrock credentials were ever wired up, and every
other agent in this repo already runs on `OPENAI_API_KEY` /
`openai/gpt-4o-mini`. Set `HR_TEAM_MODEL` / `HR_TEAM_API_KEY` in `.env` if
you want this crew back on Bedrock (or a different provider) once credentials
exist — nothing else needs to change.

## Known limitations carried over from the prototype

- **No delivery transport.** `notify_person` queues to `crews/hr/outbox.jsonl`
  and reports "queued" — true today, since there's no Telegram/Slack bot
  draining that file yet. Swap `notify.py`'s `_deliver` for a real transport
  and nothing else changes.
- **`WorkloadResponse.needs_reply` is recorded but not acted on.**
  `_run_hr_team` appends the pending question to
  `OrchestratorState.pending_actions`, and `api/entrypoint.py` already carries
  that field across turns — but nothing reads it. So a WARN verdict asks the
  founder to confirm and then forgets it: their "yes" comes back in as a fresh
  turn the Orchestrator routes from scratch. Closing this is Section 4 of
  `plans/workload_manager.md` (a real `pending_approval` in `api/sessions.py`,
  checked in `POST /chat` before `run_orchestrator`), and it's the same shape
  as `crews/document`'s escalation gate being "built, but not wired in".
- **`headcount_plan` for grant requests still comes from
  `knowledge/documents/headcount_plan.json`**, per `crews/document/README.md`
  — swap that loader call in `OrchestratorFlow._dispatch_grant` for a real
  call into this crew (e.g. `get_team_roster` + `get_capacity_forecast`) now
  that a real HR crew exists.
- **Agent-level execution knobs** (`max_iter`, `max_rpm`,
  `max_execution_time`, `max_retry_limit`, `cache`, `respect_context_window`)
  are ported from the prototype's `agents/hr_manager.jsonc` `settings` block.
  They aren't used by any other Python agent in this repo, but the
  constructor accepts all of them on `crewai` 1.15.20 (verified — the test
  suite builds `hr_manager_agent` at import time, so a rejected field would
  fail collection). If a future `crewai` bump rejects one, drop that single
  field rather than the whole port.

## Running the tests

```bash
pytest src/tests -v
```

`test_hr_ledger.py` (ported from the prototype's `test_ledger.py`) exercises
`ledger.py`/`safety.py` directly — pure Python, no LLM, no API key, every
branch of `check_assignment_safety` covered at its threshold boundaries.
`test_hr_crew.py` and the HR-path tests in `test_orchestrator_flow.py`
monkeypatch `hr_manager_agent.kickoff`, so no LLM API key is needed to run
those either.

## Setup — seed the ledger first

**Required once per machine, before anything HR-related will work:**

```bash
cd src && python -m crews.hr.seed
```

`workload.db` is gitignored, so a fresh clone has no ledger at all and every
tool returns `ERROR: ...` until you run this. It's safe to re-run whenever you
want fresh demo data — `seed.py` resets the four tables and rebuilds them
relative to today's date, which is exactly why the file isn't committed: the
overload streak that makes Priya BLOCK is anchored to the current ISO week.

`test_hr_ledger.py` builds its own throwaway ledger and doesn't touch this
file, so the tests pass on an unseeded clone. A live `crewai`/API run does
not.
