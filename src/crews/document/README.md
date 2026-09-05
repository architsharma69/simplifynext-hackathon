# HERMES — Document Creation / Form-Filling Agent

Implements the "Statutory Compliance / Internal Financial Synthesizer /
Grant & Capital Strategist" piece of the larger BRO system, as a `CrewAI`
Flow hosted behind `FastAPI`.

This repository is organised to match the structure of the top-level BRO
hackathon repo (`simplifynext-hackathon`): `Config/`, `src/api`, `src/flows`,
`src/crews`, `src/tests`, with `pytest.ini`, `requirements.txt` and this
`README.md` at the root.

## Layout

```
simplifynext-hackathon/
  Config/
    config.py             Path & runtime config (ROOT/SRC/CONFIG, document output dir)
  src/
    main.py               Entry point (runs uvicorn) 
    models.py             Pydantic data contracts (CompanyProfile, FinancialForecast,
                           GrantPackage, EscalationRequest, ...)
    api/
      entrypoint.py       run_orchestrator() — the single doorway from HTTP into the Flow
      main.py             FastAPI service: /health, /hermes/message, /hermes/review
      sessions.py         HermesState persistence keyed by platform+user_id
    flows/
      orchestrator_flow.py  HermesFlow: top-level orchestrator / state machine
      state.py              HermesState (the Flow state object)
      escalation.py         Human-in-the-loop state machine (request/resolve/check)
    crews/
      agents.py           The 3 CrewAI Agents, each scoped to its own toolset
      tasks.py            Task templates bound to those agents
      crews.py            One-Crew-per-domain wrappers invoked from the Flow
      tools/
        statutory_tools.py  ACRA docx rendering (Model Constitution, Form 45,
                             First Board Resolution, RORC register) + validation
        financial_tools.py  Deterministic 3yr cash flow / P&L / burn-rate calc
        grant_tools.py       Grant package (Startup SG Founder / EDG) compiler
    tests/
      test_orchestrator_flow.py  Flow routing & escalation behaviour
      test_entrypoint.py         run_orchestrator memory across turns
      test_api.py                FastAPI endpoints (TestClient)
  README.md
  pytest.ini               pythonpath = src
  requirements.txt
```

## How it fits the wider system

- `api/main.py` is the FastAPI service. Streamlit and the Telegram bot call
  `POST /hermes/message` as pure HTTP clients — same pattern as the rest of
  the system's `run_orchestrator`.
- Session state (`HermesState`) is keyed by `f"{platform}:{user_id}"`,
  matching the "session state keyed by platform + user identity" decision.
- `flows/orchestrator_flow.py`'s `HermesFlow` is a `CrewAI` `Flow[HermesState]`
  acting as the local state machine: it decides which of the three Crews to
  invoke next based on what's already in `state`, mirroring the hybrid
  Flow-orchestrates / Crew-executes architecture used at the top level.

## Human escalation flow

1. A document-rendering tool (`render_acra_document`, `compile_grant_package`)
   produces a file and returns a `RenderedDocument`.
2. `orchestrator_flow.py` calls `escalation.request_escalation(...)` for
   anything in `FILINGS_REQUIRING_ESCALATION`, which sets status to
   `PENDING_REVIEW` and returns immediately — the Flow does **not** block
   waiting for a human.
3. Every re-entry into `HermesFlow` starts at `check_escalations`, which
   refuses to do new filing work while anything is `PENDING_REVIEW`.
4. A reviewer calls `POST /hermes/review` (approve/reject/comment). The next
   time the user (or a poller) hits `/hermes/message`, the Flow picks up the
   resolution and continues.

## Running locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...   # or whichever provider crews/agents.py's LLM() targets
uvicorn api.main:app --app-dir src --reload
```

Or through the entry point:

```bash
python src/main.py
```

> **CrewAI compatibility note** — the code is written against CrewAI 1.x
> (verified on 1.15.18). Rehydrating a session passes the whole `HermesState`
> through the `Flow` constructor's `initial_state` parameter, and the handler
> names are decoupled from their event strings (so a listener is never
> triggered by its own completion). With an older CrewAI these behaviours
> differ, so keep `crewai` at 1.x. The `[anthropic]` extra is required for
> `LLM(model="claude-sonnet-4-6")`.

The API serves:
- `GET /health` — liveness check.
- `POST /hermes/message` — body `{"platform", "user_id", "user_message", ...optional structured payloads}`.
- `POST /hermes/review` — body `{"session_id", "escalation_id", "approve", "reviewer_id", "comment"}`.
- `GET /hermes/session/{platform}/{user_id}/pending-reviews` — pending escalations for a session.

## Running the tests

```bash
pytest src/tests -v
```

`pytest.ini` sets `pythonpath = src`, so tests import `api.*`, `flows.*`,
`crews.*` and `models` as package modules. The flow tests monkeypatch the
crew entry points with canned JSON so no LLM / API key is needed.

## What's stubbed vs. production-ready

- **Production-ready logic**: financial forecast math, ACRA docx rendering,
  the escalation state machine's semantics, the Pydantic data contracts.
- **Stubbed for illustration** (clearly marked in comments):
  - `api/sessions.py` and `flows/escalation.py` use in-memory dicts — swap
    for Redis/Postgres.
  - `orchestrator_flow.py`'s parsing of Crew string output into typed objects
    should be replaced with CrewAI's `Task(output_pydantic=...)` for reliability.
  - Financial assumptions / grant narrative sections are assumed to already
    be extracted into structured fields by the conversational layer before
    hitting `/hermes/message` — the actual "ask the user for missing fields"
    conversational loop lives in the agents' prompts / the wider Flow, not
    duplicated here.
  - Docx templates are built directly with `python-docx` rather than ACRA's
    actual official form templates (not publicly redistributable) — swap
    `_render_*` bodies for `docxtpl` renders of the real templates once you
    have them.
