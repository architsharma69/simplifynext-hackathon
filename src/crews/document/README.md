# Document crew — statutory filings, financial forecasts, grant packages

Implements the "Statutory Compliance / Internal Financial Synthesizer / Grant &
Capital Strategist" piece of the larger BRO system: the `document` specialist
that `flows/orchestrator_flow.py`'s `OrchestratorFlow` can route to.

## Layout

```
src/crews/document/
  agents.py           Four standalone CrewAI Agents, none holding tools:
                       statutory_compliance_agent, financial_synthesizer_agent,
                       grant_strategist_agent, and document_team_lead_agent
                       (routing only). See "Why no tools" below.
  tasks.py             Plain prompt-string builders for the Team Lead's routing
                       call and each specialist's narration-only kickoff — no
                       crewai.Task/Crew objects (see "Why no Crews" below).
  schemas.py           Pydantic data contracts (CompanyProfile, FinancialForecast,
                       GrantPackage, EscalationRequest, DocumentRoutingDecision, ...)
  escalation.py        Human-in-the-loop state machine (request/resolve/check).
                       Built, but NOT currently wired into the flow — see below.
  tools/
    statutory_tools.py  ACRA docx rendering (Model Constitution, Form 45,
                         First Board Resolution, RORC register) + validation
    financial_tools.py  Deterministic 3yr cash flow / P&L / burn-rate calc
    grant_tools.py       Grant package (Startup SG Founder / EDG) compiler
```

## How it's actually invoked

There's no separate "document flow" or hidden dispatch module. The Document Team
Lead is realized as more steps in the *same* `OrchestratorFlow` that does
top-level routing:

1. `OrchestratorFlow.route_document()` (in `flows/orchestrator_flow.py`) fires
   when the top-level Orchestrator picked `"document"` as a specialist for this
   turn. It calls `self._run_document_team(sub_query)`.
2. `_run_document_team` builds a routing prompt (`tasks.build_document_routing_prompt`)
   from the rephrased query plus `OrchestratorState.business_context`, and asks
   `document_team_lead_agent` for a structured `DocumentRoutingDecision`: which ONE
   specialist applies, plus the request-specific choices that data can't answer
   (which ACRA document types, which grant scheme, requested amount).
3. `OrchestratorFlow._dispatch_statutory` / `_dispatch_financial` / `_dispatch_grant`
   load that specialist's reference data straight from `knowledge/documents/*.json`
   (see "Knowledge base" below) and call every deterministic tool it needs
   **directly in Python** — `validate_company_profile.run(...)`,
   `render_acra_document.run(...)`, `generate_financial_forecast.run(...)`,
   `summarize_burn_and_breakeven.run(...)`, `validate_grant_narrative.run(...)`,
   `compile_grant_package.run(...)` — validating each result against the real
   Pydantic models (`CompanyProfile`, `HeadcountPlan`, `RenderedDocument`,
   `FinancialForecast`, `GrantPackage`) before doing anything with it. Only once
   that's all done does it call the specialist agent —
   `statutory_compliance_agent.kickoff(...)`, `financial_synthesizer_agent.kickoff(...)`,
   or `grant_strategist_agent.kickoff(...)` — handing it the already-computed
   result to narrate in plain English. A grant request auto-chains the financial
   dispatch first if no forecast is cached yet this session.

## Why no tools

Earlier versions of `agents.py` gave each specialist the matching CrewAI tools
(`validate_company_profile`/`render_acra_document` on the statutory agent, etc.)
and let the LLM call them. In practice, smaller/cheaper models (this crew
defaults to `openai/gpt-4o-mini` via `Config.DOCUMENT_TEAM_MODEL`) would
occasionally invent the wrong shape of argument for a tool — e.g. calling
`generate_financial_forecast` (which needs 5 named numbers) with a
self-fabricated `{"months": [...]}` object, as if the tool wanted the
*computed result* rather than the *inputs* — which surfaces as a Pydantic
"Field required" error at the tool-call boundary. Every one of these tools is
fully deterministic, so there's no reason to route their arguments through an
LLM at all: `OrchestratorFlow` calls them directly (see above), and each
specialist agent's only remaining job is turning an already-computed,
already-validated result into a plain-English sentence for the business
owner — a job with no tool-call arguments to get wrong.

## Knowledge base

`src/knowledge/documents/*.json` holds the sample company/business data every
document specialist needs — `company_profile.json`, `financial_assumptions.json`,
`grant_narrative.json`, `headcount_plan.json` — checked into the repo for the
hackathon instead of being gathered live via conversation. `knowledge/documents/__init__.py`
exposes one loader per file (`load_company_profile()`, etc.); each `_dispatch_*`
method calls the loader(s) it needs directly and feeds the result straight into
the relevant deterministic tool call — no LLM extraction step for this data, no
flow state. `DocumentRoutingDecision` only carries what the knowledge base
*can't* answer: which specialist, which ACRA document types, which grant
scheme, how much funding.

A `ValidationError` against one of these files means the fixture itself doesn't
match its schema — a repo bug, not something the business owner can fix by
answering a question — so `_describe_validation_errors` phrases that case as an
internal error rather than a clarifying question.

## Why no Crews

Each specialist works alone (`allow_delegation=False` on all of them) — there's no
inter-specialist delegation happening, so wrapping each one in its own single-agent
`Crew` added coordination machinery (`Task`, `Process`, `context=[...]`) that this
domain doesn't need. Specialists are called directly via `Agent.kickoff(...)`, the
same call `crews/orchestrator/agent.py` already uses for the top-level Orchestrator
— and all the deciding/validating/sequencing/tool-calling logic lives in
`OrchestratorFlow` itself, not hidden behind a separate dispatch module.

## Human escalation — built, but intentionally not wired up yet

`escalation.py` implements the full gate: a document tool calls
`request_escalation(...)` after rendering, which flips status to `PENDING_REVIEW`;
a reviewer calls `resolve_escalation(...)`; `has_pending_escalations(session_id)`
should block new filing work until resolved. **None of this is called from
anywhere yet** — a rendered Model Constitution / Form 45 goes straight back to the
user today with no human sign-off gate.

This is a deliberate scope decision, not an oversight: wiring it up needs a
`session_id` threaded through `OrchestratorState`/`entrypoint.py`/the API, a new
review endpoint, and — more importantly — a reviewer identity/UI, since the person
approving a filing is not the business owner chatting in Streamlit
(`ui/streamlit/app.py` has no reviewer-facing screen at all today). Treat this as a
follow-up, not something quietly missing.

## Known limitations carried over from the placeholder system

- `headcount_plan` for grant requests comes from `knowledge/documents/headcount_plan.json`
  rather than a real HR crew (`flows/placeholders.run_hr` is still a stub) — swap the
  loader call in `_dispatch_grant` for a real HR crew's output once one exists.
- Docx templates are built directly with `python-docx` rather than ACRA's actual
  official form templates (not publicly redistributable) — swap the `_render_*`
  bodies in `tools/statutory_tools.py` for `docxtpl` renders of the real templates
  once you have them.
- Rendered documents are written under `Config.DOCUMENT_OUTPUT_DIR`
  (`HERMES_DOCUMENT_DIR` env var to override) and registered with `api/documents.py`
  so `ui/streamlit/app.py` can offer them as real downloads via
  `GET /documents/{document_id}`.

## Running the tests

```bash
pytest src/tests -v
```

`pytest.ini` sets `pythonpath = src`. `test_document_crew.py` and the
document-path tests in `test_orchestrator_flow.py` monkeypatch every specialist
agent's `.kickoff`, so no LLM API key is needed to run them.
