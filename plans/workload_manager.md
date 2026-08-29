# The Solution
Problem: Start up founders want to just focus on ideas, not need to master the intricacies of business management

# The Agent 
The HR agent basically keeps a ledger on all the employees in the startup. It keeps track of their working hours, their workload, their upcoming tasks. It compiles the data and compares it with rest of the employees within the same department to ensure work load distribution fairness and to protect employee safety.


# Building the Tools
- Create /crews/hr/db/schema.sql with four tables: people, tasks, workload_log, wellbeing_events.

- Write /crews/hr/db/seed.py populating a believable 8-person startup — including one engineer deliberately at ~130% capacity for three consecutive weeks, so the burnout catch is demonstrable on stage rather than hypothetical.

- Implement the four read functions: get_team_roster(), get_person_schedule(name, week), list_open_tasks(status, due_before), get_capacity_forecast(weeks).

- Implement the four write functions: create_task(...), assign_task(task_id, person_id), update_task_status(task_id, status), log_wellbeing_event(person_id, type, note).

- Implement check_assignment_safety(person, est_hours, due_date). This function does not request the LLM and therefore can't influence the answer. It returns OK / WARN / BLOCK plus a reason string.  Rules: >100% weekly capacity, third consecutive overloaded week, or assignment during logged leave → BLOCK; 85–100% capacity or an out-of-hours deadline → WARN. The value 85-100 % is just a placeholder value and can be set by the founder.

- Unit test every ledger function and every branch of the safety rules with pytest before any agent exists — this is the layer a better prompt cannot rescue.

- Wrap each function as a CrewAI tool: BaseTool subclass with an args_schema for the writes and the safety check, @tool decorator for the simple reads.

- Write each tool description as an instruction to the model, not as documentation — e.g. "MUST be called before assign_task. Returns OK, WARN or BLOCK with a reason." These strings are prompts and will be the main thing you tune later.

- Hard-wire assign_task to raise unless check_assignment_safety has already returned a verdict for that exact (person, task) pair in the current request — the guardrail is a precondition in code, not a suggestion in the prompt.

- Add notify_person(person_id, message) as a thin wrapper that returns a structured payload for the UI layer to deliver, rather than sending anything itself.


# Create the Workload Manager Agent and Crew
- Define role, goal and backstory in /crews/hr/config/agents.yaml — backstory should carry disposition and tie-breaking judgement (protective of the team, blunt with the founder, trusts the ledger over anyone's optimism, never speculates about a person's performance), not hard rules.

- Set allow_delegation=False — this agent answers or refuses; it does not hand work to other agents. Delegation makes demos unpredictable and burns tokens.

- Point the agent at the central LiteLLM config from Section 2 rather than hardcoding a model string.

- Define three tasks in /crews/hr/config/tasks.yaml: assess_capacity, allocate_work, burnout_scan.

- Add Allocation, TeamStatus and BurnoutFlag Pydantic models to /shared/schemas.py — the same file the Orchestrator, Finance and Document crews import from.

- Set output_pydantic on each task so downstream consumers get structured JSON instead of prose they would have to re-parse.

- Freeze /shared/schemas.py with the whole team before building against it  
- Finance pulls hours-per-person for payroll and burn, and both UIs render        Allocation. A late schema change breaks three people's work.

- Scaffold /crews/hr/crew.py with a @CrewBase class exposing hr_crew(), using Process.sequential for now.

- Test the crew in isolation with read-only queries ("who's free this week?") before wiring it into the Flow — confirm it reaches for tools rather than confabulating numbers.
 

# Wire the Workload Manager Sub-Flow
- Define WorkloadState(BaseModel) in /crews/hr/state.py: request_id, message, draft, verdict, reason, awaiting_approval, reply.
 
- Scaffold WorkloadFlow(Flow[WorkloadState]) with @persist, invoked from OrchestratorFlow's HR @listen step with the relevant slice of shared state.

- Add @start() receive that takes the sub-query the Orchestrator routed to this crew.

- Add @listen steps for the read-only paths (answer_query, record_event) that call hr_crew().kickoff() and return immediately.

- Add @listen("allocate") propose_allocation that calls the crew and writes the resulting Allocation into state.draft.

- Add @router(propose_allocation) safety_gate that calls check_assignment_safety() and returns "ok" / "warn" / "block" — no model call in this router.
 
- Add @listen("ok") commit that calls assign_task and writes the result to state.

- Add @listen("warn") ask_confirmation and @listen("block") refuse_and_suggest — both set awaiting_approval=True, return needs_reply: true, and end the flow rather than blocking.

- Have refuse_and_suggest call suggest_alternatives(draft) so a refusal always arrives with a next-best option (different person, or a later date).

- Converge every branch on a single @listen(or_(...)) respond step so the UI layer has exactly one payload shape to render.

- Include the verdict and reason in the response payload, so both UIs can surface why an assignment was blocked.

- Add step-level logging (which branch fired, verdict, tool calls) into the Section 1 tracing so the guardrail is visible in the demo.


# Handle Asynchronous Approval Across Both UIs
- Extend the Section 3 session store with a pending_approval field per (platform, user_id): {request_id, draft, verdict, created_at}.

- Do not use CrewAI's human_input=True — it blocks on stdin inside kickoff(), which cannot work over Telegram where the reply arrives on a different HTTP request minutes later.

- In POST /chat, check pending_approval for that session before calling run_orchestrator() — if it is set, route the message to the approval handler instead of the Orchestrator.

- Implement ApprovalFlow(Flow[WorkloadState]) with @persist, restored via kickoff(inputs={"id": request_id}), and a @router returning "confirmed" / "abandoned".

- On "confirmed": write a override_approved row to wellbeing_events before calling assign_task — an overridden block must leave a trace.

- On "abandoned": leave the task unassigned and reply with a short acknowledgement.

- Handle ambiguous replies ("maybe", "hmm") by re-asking once, then dropping the pending approval rather than guessing.

- Clear pending_approval on every terminal outcome, including errors.

- Add an expiry (e.g. 30 minutes) so a forgotten approval doesn't hijack the founder's next unrelated message.

- Test the full pause-and-resume on Telegram and Streamlit concurrently to confirm session isolation — a pending approval in one must not leak into the 
other.

# Burnout Watch (scheduled path)
- Build BurnoutFlow as a separate flow that is not triggered by a user turn — it scans, it does not converse.

- @start() scan_all_people reads workload_log and wellbeing_events and produces a list of BurnoutFlag objects.

- @router returns "flagged" or "none"; "none" exits silently rather than sending an all-clear message.

- @listen("flagged") notify_founder produces a structured summary payload for whichever UI the founder last used.

- Add a manual trigger button in the Streamlit sidebar so the burnout catch can be demonstrated on demand, plus a scheduled nightly run for the "in production this just happens" story.

- Confirm it does not run on every user turn — it is the most expensive path and adds nothing to a normal request.



