# crews

One subfolder per department's agent(s), each self-contained (its own prompts, schemas, and Python wiring). Currently:

- `orchestrator/` — the Orchestrator: routes questions to the right department, rephrasing them along the way, or answers directly when no department applies. See its own README for details.
- `document/` — Statutory Compliance / Internal Financial Synthesizer / Grant & Capital Strategist. See its own README for details.
- `hr/` — the HR / Workload Manager: tracks the team roster, task load and capacity, and enforces the assignment safety guardrail before placing work on anyone. See its own README for details.

More departments (Finance, Consultant) will be added here later, each following the same file pattern as `orchestrator/`.
