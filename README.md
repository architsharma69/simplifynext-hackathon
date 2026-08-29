# Implementation Plan: Business Resiliance Operator (BRO) (V1.1)
## Framing of our solution
Problem: Start up founders want to just focus on ideas, not need to master the intricacies of business management. Many of these ideas have the potential to do so much good. However, the peripheral aspects of business management impede the possibility of this future benefit. These periphal aspects can come in the form of:
* HR, Finance and Logistics departments
* Formalities such as filling out forms, posting regular expense reports, writing grant and loan applications.
* Understsanding business / economic jargon, being tech-savvy in order to use varying user interfaces when doing business on multiple platforms.

## Architecture of the solution
* Orchestrator
* HR agent (workload manager, keeps track of employees and rosters)
* Document generation agent
* Finance agent
* Consultant agent

**Agentic Framework**: `CrewAI`, a python module that creates the entire architecture of the agentic app: creating individual agents (the `Agent` bject), teams of agents (the `Crew` object), and a custom workflow (the `Flow` object) that decides how the user input is processed.

**UI**: As it currently is, the user only needs to send text queries to the orchestrator agent. The main thing our UI needs to do is accept user input and pass it to the agentic workflow, then return all responses (including documents) back to the user. So we really need just a lightweight UI. `Streamlit` is a python library that can design these very easily, doesn't need us to use any other languages, so I suggest we use it.

**Architecture decision:** Hybrid model — a CrewAI **Flow** acts as the top-level orchestrator/state machine, and each specialist (HR, Document Generation, Finance, Consultant) is implemented as its own **Crew**, invoked as a step within the Flow. This gives explicit, debuggable control flow at the top while still letting each domain crew use CrewAI's native agent/task/delegation patterns internally.

**Backend decision:** A single shared Python function/module (`run_orchestrator(user_input, session_state)`) contains all Flow logic, hosted behind a single FastAPI service. Both Streamlit and the Telegram bot are pure HTTP clients of this API — neither talks to the other, and neither imports the Flow logic directly. Session state is keyed centrally by platform + user identity (e.g. `streamlit_session_id`, `telegram_user_id`) and managed on the API side.

### Core differentiating features of our solution
1. An evolving system, with a growing memory base, consultant agent which designs new tools, targets
2. Cross-Agent Negotiation, different agents argue and make their case for why a certain decision should be made / should not be made before arriving at a decision
3. Human escalation / verification for certain steps
4. Exposes a simple UI using a telegram bot, makes it more accessible to less tech-savvy business owners


---


## Todos
GAVIN: Document creation for financials (explore what is needed by small businesses)
Archit: Easy interface for people that is not tech savvy (like connects to a whatsapp chat / tele bot)
Archit: simulation feature (possibly scope down and maybe incorporate into an existing feature)
