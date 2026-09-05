# crews

One subfolder per department's agent(s), each self-contained (its own prompts, schemas, and Python wiring). Currently:

- `orchestrator/` — the Orchestrator: routes questions to the right department, rephrasing them along the way, or answers directly when no department applies. See its own README for details.

More departments (workload manager/HR, Finance, Document, Consultant) will be added here later, each following the same file pattern as `orchestrator/`.