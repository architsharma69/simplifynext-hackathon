# Business Resiliance Operator (BRO) (V1.1)
## Framing of our solution
Problem: Start up founders want to just focus on ideas, not need to master the intricacies of business management. Many of these ideas have the potential to do so much good. However, the peripheral aspects of business management impede the possibility of this future benefit. These periphal aspects can come in the form of:
* HR, Finance and Logistics departments
* Formalities such as filling out forms, posting regular expense reports, writing grant and loan applications.
* Understanding business / economic jargon, being tech-savvy in order to use varying user interfaces when doing business on multiple platforms.

## System Architecture (as built)
The three main agentic entities are:
* Orchestrator
* HR agent (workload manager, keeps track of employees and rosters)
* Document generation agent (a team lead plus three filing/finance specialists)

### How the Orchestrator decides

Every message first goes to the Orchestrator agent, which returns exactly one of three outcomes:

- **`clarify`** — it genuinely can't tell what's being asked, even to route it, so it asks the owner one clarifying question back instead of guessing.
- **`direct`** — nothing any specialist handles applies (small talk, greetings, meta questions about the assistant), so the Orchestrator answers the owner itself.
- **`delegate`** — one or more specialists can help. The Orchestrator rephrases the owner's question into a clear, standalone version for each specialist it picks (they never see the owner's original wording), those specialist branches run, and once all of them finish, the Orchestrator synthesizes their outputs into one coherent response — calling out conflicts explicitly rather than silently picking a side.

### The agents

| Agent | Role | What it does |
|---|---|---|
| **Orchestrator** | Single point of contact for the business owner | Classifies each message into clarify/direct/delegate, rephrases sub-questions for whichever specialist(s) it picks, and synthesizes their outputs into one response |
| **HR Manager** (Chief of Staff) | Keeps every person's real workload visible so nobody quietly burns out | Places or reassigns tasks against the team roster and capacity — gated by a hard Python safety check, not just an LLM judgment call — logs wellbeing events, and notifies people directly |
| **Document Team Lead** | Triages incoming document requests | Reads a rephrased document request and decides which one of the three specialists below should handle it, pulling out structured facts (e.g. grant scheme, requested amount) along the way |
| **Statutory Compliance Specialist** | Singapore ACRA incorporation expert | Validates a company's profile against Companies Act 1967 requirements, then renders the required filings (Model Constitution, Form 45/45B, Board Resolutions, Register of Registrable Controllers) |
| **Internal Financial Synthesizer** | Reviews a startup's 3-year financial forecast | Flags implausible assumptions (e.g. negative COGS, unrealistic growth) and writes a plain-English summary — the forecast itself is computed deterministically in Python, never by the LLM |
| **Grant & Capital Strategist** | Singapore grant-writing consultant | Compiles a complete Startup SG Founder or EDG grant package from the financial forecast and headcount plan already produced by other specialists |

### The two UIs

Both the Streamlit dashboard and the Telegram bot are thin, independent clients of the same FastAPI backend (`POST /chat`) — neither talks to the other, and neither imports any Flow or agent logic directly. Session state lives server-side, keyed by platform + user identity, so a user's conversation history and business context follow them regardless of which UI they're using.

As of now, the way to run the UIs is to host them locally on the machine this project folder is running on.

#### Note
While we would have much preferred to deploy the API and both UIs, we have had a lot of trouble accessing the AWS accounts that were allocated to us. The password that I, the team leader, had set, was not working. 

I tried all provided ways to reset the password, but those didn't work. We emailed the main point of contact for the hackathon, who told us to wait as their tech team works on a solution. That was on the 2nd of August, and we didn't get any response till now despite several further prompts.

#### Note on testing multiple UIs at once
As of now, our 2 UIs are not made to be run simultaneously. To avoid any unexpected outcomes, please test out each UI one at a time, and make sure to shut down the UI once done testing to ensure the locally hosted processes don't persist past testing.

See **TEST_GUIDE_FOR_JUDGES.md** for exact step-by-step instructions on running and testing both.

### Core differentiating features of our solution
1. An evolving system, with a growing memory base, consultant agent which designs new tools, targets
2. Cross-Agent Negotiation, different agents argue and make their case for why a certain decision should be made / should not be made before arriving at a decision
3. Human escalation / verification for certain steps
4. Exposes a simple UI using a telegram bot, makes it more accessible to less tech-savvy business owners
