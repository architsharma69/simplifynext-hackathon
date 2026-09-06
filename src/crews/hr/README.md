# HR crew — workload manager

Implements the "HR agent (workload manager, keeps track of employees and
rosters)" piece of the larger BRO system: the `hr` specialist that
`flows/orchestrator_flow.py`'s `OrchestratorFlow` routes to.

This started as a port of a standalone CrewAI prototype
(`plan/workload_manager/` — JSON-config crew + SQLite ledger + Python safety
guardrail, built and unit tested independently). The SQLite ledger has since
been replaced with a static JSON knowledge-base fixture, matching how
`crews/document` sources its reference data — see "Why no ledger" below.

## Layout

```
src/crews/hr/
  agents.py        hr_manager_agent — one standalone CrewAI Agent, six tools,
                    no team-lead routing step (there's only one HR agent).
  tasks.py          build_hr_prompt(sub_query, today, team_snapshot_json) —
                     the ordered procedure prompt, with the team snapshot
                     injected directly into it.
  schemas.py        WorkloadResponse and friends (Allocation, TeamStatus, ...) —
                     the typed contract hr_manager_agent returns.
  roster.py         Read-only data access over knowledge/hr/team_roster.json —
                     workload math (assigned_hours, effective_capacity,
                     overload_streak, ...) plus build_snapshot(), which
                     computes everything hr_manager_agent needs for
                     injection into its prompt. Pure Python, unit-testable
                     with no API key and no model.
  safety.py         check_assignment_safety() — the actual guardrail.
                     Deterministic OK/WARN/BLOCK: 85% load warns, 100%
                     blocks, 3 consecutive overloaded weeks blocks. Reads
                     through roster.py; the rules themselves are unchanged
                     from the original prototype.
  notify.py         notify_person() — queues to outbox.jsonl. No delivery
                     transport (Telegram/Slack) exists yet; see below.
  tools/            Six thin BaseTool wrappers — see "Why BaseTool, not
                     @tool" below.
```

`knowledge/hr/team_roster.json` (loaded via `knowledge/hr/__init__.py`,
mirroring `knowledge/documents/__init__.py`) holds the people, their
skills/capacity/contact info, and the current task list — the sample data
that used to live in the seeded `workload.db`. Its dates are offsets
(`due_offset_days`, `start_offset_days`, ...) relative to the Monday of the
current week, resolved to real ISO dates by `roster.py` at call time, so the
fixture (Priya deliberately overloaded, Wei Ling on leave Thu/Fri) stays
correct no matter what day it's actually run — no seed script, no database
to regenerate.

## How it's actually invoked

Same pattern as the document crew:

1. `OrchestratorFlow.route_hr()` fires when the top-level Orchestrator picked
   `"hr"` as a specialist for this turn.
2. It calls `self._run_hr_team(sub_query)`, which calls
   `roster.build_snapshot()` for the team's current state, builds the
   procedure prompt (`tasks.build_hr_prompt`) with that snapshot injected
   directly into it, and calls
   `hr_manager_agent.kickoff(prompt, response_format=WorkloadResponse)`.
   `_run_hr_team` never gathers roster/workload data itself beyond calling
   `build_snapshot()` — same shape as `_dispatch_statutory` etc. loading
   `knowledge/documents/*.json` straight into their specialists' prompts.
3. `hr_manager_agent` works the procedure using the injected snapshot for
   anything read-shaped, and its remaining tools for the safety check and
   write-shaped confirmations — always calling `check_assignment_safety`
   before `assign_task`, exactly as the prompt instructs.
4. The structured `WorkloadResponse.message` (falling back to the raw text if
   structured parsing fails) is what lands in
   `OrchestratorState.active_agent_outputs["hr"]` for the final synthesis
   step — the founder-readable sentence, not the whole JSON object.

## Why no ledger

The original prototype (and this repo's first port of it) used a SQLite
ledger + ten read/write tools so the agent could query and mutate live
state — a reasonable design for a real deployment, but more moving parts
(a gitignored DB, a seed script to run before anything worked, four
tool-call round trips just to read data already known up front) than a
hackathon demo needs. `crews/document` never had this problem: its
reference data is a handful of static JSON fixtures injected straight into
each specialist's prompt.

This crew now follows the same pattern:

- **Reads are gone as tools.** `get_team_roster`, `get_person_workload`,
  `list_open_tasks` and `get_capacity_forecast` no longer exist —
  `roster.build_snapshot()` computes the equivalent of all four in one call
  and `_run_hr_team` injects the result directly into the prompt (see
  `crews/hr/tasks.py`). The agent never needs to ask for data it's already
  been handed.
- **Writes are stateless.** `create_task`, `assign_task`,
  `update_task_status` and `log_wellbeing_event` still exist as tools —
  they still validate their inputs, and `assign_task` still refuses without
  a `check_assignment_safety` verdict and refuses a `BLOCK` outright — but
  none of them persist anywhere any more. Each confirms what *would* happen
  and returns, exactly as if it had; nothing written in one request is
  visible to the next. For a single-turn demo (found, evaluate, refuse-or-
  confirm) this is invisible; it only matters if a *later, separate*
  request depends on an earlier one's assignment sticking — it won't.
- **The guardrail itself didn't change.** `check_assignment_safety`'s rules
  and thresholds are untouched — only its data source moved from SQLite
  rows to `roster.py`'s reads over the JSON fixture, keyed by name instead
  of a database id.

If a future need reintroduces real persistence (a live multi-turn demo
where assignments must stick, or moving past the hackathon), the natural
next step is a small in-memory store seeded from the same JSON fixture at
process start, so the write tools mutate that instead of returning
confirmations against a static snapshot.

## The safety guardrail

`tools/assign_task.py` raises unless it is handed a `safety_verdict` that
came from `check_assignment_safety`, and refuses outright on `BLOCK` — this
is enforced in plain Python, not in the prompt, so it can't be talked around
by the model. It adds one thing on top: when it refuses, it calls
`safety.suggest_alternatives` and appends who *would* pass, so a refusal
always comes with an option instead of a dead end.

## Why BaseTool, not `@tool`

`crews/document/tools/*.py` use CrewAI's `@tool(...)` decorator. These use
class-based `BaseTool` subclasses instead — both are valid CrewAI tool
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

## Known limitations

- **No delivery transport.** `notify_person` queues to `crews/hr/outbox.jsonl`
  and reports "queued" — true today, since there's no Telegram/Slack bot
  draining that file yet. Swap `notify.py`'s `_deliver` for a real transport
  and nothing else changes.
- **`WorkloadResponse.needs_reply` is recorded but not acted on.**
  `_run_hr_team` appends the pending question to
  `OrchestratorState.pending_actions`, and `api/entrypoint.py` already carries
  that field across turns — but nothing reads it. So a WARN verdict asks the
  founder to confirm and then forgets it: their "yes" comes back in as a fresh
  turn the Orchestrator routes from scratch. This is the same shape as
  `crews/document`'s escalation gate being "built, but not wired in".
- **`headcount_plan` for grant requests still comes from
  `knowledge/documents/headcount_plan.json`**, per `crews/document/README.md`
  — swap that loader call in `OrchestratorFlow._dispatch_grant` for a real
  call into `roster.py` (e.g. `get_team_roster` + `get_capacity_forecast`)
  if headcount planning should reflect the same team data HR uses.
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

`test_hr_roster.py` exercises `roster.py`/`safety.py` directly — pure
Python, no LLM, no API key, every branch of `check_assignment_safety`
covered at its threshold boundaries. Each test builds its own tiny team
fixture and monkeypatches `roster.load_team_roster` to return it, rather
than seeding a throwaway database. `test_hr_crew.py` and the HR-path tests
in `test_orchestrator_flow.py` monkeypatch `hr_manager_agent.kickoff`, so
no LLM API key is needed to run those either.

There is no setup step required before a live run any more — a fresh clone
already has `knowledge/hr/team_roster.json` checked in.
