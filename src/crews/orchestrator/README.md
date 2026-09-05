# orchestrator

The Orchestrator is a standalone CrewAI `Agent` (not a `Crew` — it doesn't need one, since it does no multi-step or multi-agent work of its own). Its job is purely to route or answer, never to do specialist work itself.

## `__init__.py`
Empty. Just marks this folder as a Python package.

## `config/agents.yaml`
Not code — the Orchestrator's prompt. One entry, `orchestrator`, with `role`/`goal`/`backstory` text telling it: never do specialist work yourself, rephrase the question clearly when delegating, or answer plainly yourself when nothing any department handles applies.

## `config/tasks.yaml`
Not code — two prompt templates, filled in with real values (`{user_input}`, `{business_context}`, `{specialist_outputs}`) before being sent to the agent.

- `routing_task` — asks the LLM to choose exactly one `route_type` (delegate to specialist(s), answer directly, or ask for clarification) for the current question.
- `synthesis_task` — asks the LLM to combine every specialist's answer into one reply for the business owner, once they've all responded.

## `schemas.py`
Pydantic models that pin down the exact shape the LLM's routing answer must come back in — no functions, just data definitions:

- `RephrasedQuery` — one specialist's name plus the rephrased question meant for them.
- `RoutingDecision` — the full routing answer: which `route_type` was chosen, which specialists to delegate to, their rephrased questions, a direct answer (if answering directly), or a clarifying question (if asking one). Every field is required (no defaults) because OpenAI's strict structured-output mode needs every field listed, even ones that end up empty/null for a given `route_type`.

## `agent.py`
The actual logic: builds the agent and asks it questions.

- `build_orchestrator_agent()` — builds a fresh CrewAI `Agent` from `agents.yaml`'s prompt text plus the model configured in `Config`.
- `_build_prompt(task_name, **kwargs)` — takes a prompt template from `tasks.yaml`, fills in the `{placeholders}` with real values, and appends the expected-output text.
- `route(user_input, business_context)` — asks the agent to make a routing decision for a question, and returns it as a validated `RoutingDecision`.
- `synthesize(user_input, specialist_outputs)` — asks the agent to combine specialist answers into one final reply, and returns that reply as plain text.