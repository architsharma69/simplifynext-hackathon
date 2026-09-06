import json
import logging
import sys
from datetime import date
from pathlib import Path

# Makes `Config` (and, via it, `src`) importable so this file works both as
# `python -m flows.orchestrator_flow` and as a direct
# `python flows/orchestrator_flow.py` run, not just via package import.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from Config.config import SRC_DIR

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from crewai.flow.flow import Flow, and_, listen, router, start
from crewai.flow.persistence import persist
from pydantic import ValidationError

from crews.document.agents import (
    document_team_lead_agent,
    financial_synthesizer_agent,
    grant_strategist_agent,
    statutory_compliance_agent,
)
from crews.document.schemas import (
    CompanyProfile,
    DocumentRoutingDecision,
    HeadcountPlan,
)
from crews.document.tasks import (
    build_document_routing_prompt,
    build_financial_prompt,
    build_grant_prompt,
    build_statutory_render_prompt,
)
from crews.document.tools.financial_tools import (
    generate_financial_forecast,
    summarize_burn_and_breakeven,
)
from crews.document.tools.grant_tools import validate_grant_narrative
from crews.document.tools.statutory_tools import validate_company_profile
from crews.hr.agents import hr_manager_agent
from crews.hr.roster import build_snapshot
from crews.hr.schemas import WorkloadResponse
from crews.hr.tasks import build_hr_prompt
from crews.orchestrator import agent as orchestrator_agent
from flows import placeholders
from flows.state import OrchestratorState
from knowledge.documents import (
    load_company_profile,
    load_financial_assumptions,
    load_grant_narrative,
    load_headcount_plan,
)

logger = logging.getLogger(__name__)


def _truncate(value: str, length: int = 120) -> str:
    return value if len(value) <= length else value[:length] + "..."


def _rephrased_query_for(routing_decision: dict, specialist: str, fallback: str) -> str:
    for entry in routing_decision.get("rephrased_queries", []):
        if entry.get("specialist") == specialist:
            return entry.get("query", fallback)
    return fallback


def _describe_validation_errors(exc: ValidationError) -> str:
    """Formats a Pydantic ValidationError against knowledge/documents/*.json.

    These files are checked-in fixtures, not conversational input, so a
    failure here means the fixture itself doesn't match its schema — a repo
    bug, not something the business owner can fix by answering a question.
    """
    fields = sorted({".".join(str(part) for part in err["loc"]) for err in exc.errors()})
    return (
        "Internal error: the knowledge-base data is missing/invalid fields: "
        + ", ".join(fields)
    )


@persist()
class OrchestratorFlow(Flow[OrchestratorState]):
    @start()
    def receive_input(self):
        logger.info("received input: %s", _truncate(self.state.user_input))

    @listen(receive_input)
    def classify_intent_step(self):
        try:
            decision = orchestrator_agent.route(
                self.state.user_input, self.state.business_context
            )
            self.state.routing_decision = decision.model_dump()
        except Exception:
            logger.exception("routing failed, falling back to clarification")
            self.state.routing_decision = {
                "route_type": "clarify",
                "specialists": [],
                "rephrased_queries": [],
                "direct_answer": None,
                "clarifying_question": (
                    "Sorry, I had trouble understanding that — could you rephrase your question?"
                ),
            }
        logger.info("routing decision: %s", self.state.routing_decision)

    @router(classify_intent_step)
    def check_confidence(self):
        route_type = self.state.routing_decision.get("route_type")
        if route_type == "clarify":
            return "clarify"
        if route_type == "direct":
            return "direct"
        return "proceed"

    @listen("clarify")
    def ask_clarification(self):
        self.state.final_response = self.state.routing_decision.get("clarifying_question") or ""
        logger.info("asking clarification: %s", self.state.final_response)

    @listen("direct")
    def answer_directly(self):
        self.state.final_response = self.state.routing_decision.get("direct_answer") or ""
        logger.info("answering directly: %s", _truncate(self.state.final_response))

    @listen("proceed")
    def route_hr(self):
        if "hr" in self.state.routing_decision.get("specialists", []):
            sub_query = _rephrased_query_for(
                self.state.routing_decision, "hr", self.state.user_input
            )
            output = self._run_hr_team(sub_query)
            self.state.active_agent_outputs["hr"] = output
            self.state.invoked_specialists.append("hr")
            logger.info("hr crew invoked: %s", _truncate(output))

    def _run_hr_team(self, sub_query: str) -> str:
        """hr_manager_agent handles the rephrased request end to end — there's
        no team-lead routing step here the way there is for crews/document,
        since HR is one agent, not several specialists to choose between.

        The team roster and current workload are never gathered here: they're
        computed by crews.hr.roster.build_snapshot() straight from
        knowledge/hr/team_roster.json and injected directly into the prompt
        (crews/hr/tasks.py), the same pattern _dispatch_statutory etc. use for
        knowledge/documents/*.json — see crews/hr/README.md.

        Returns WorkloadResponse.message (what the founder actually reads)
        rather than the full structured object, matching the plain-string
        contract every other _run_*_team-style dispatch hands back to
        synthesize_step via active_agent_outputs.
        """
        today = date.today()
        snapshot = build_snapshot(today)
        prompt = build_hr_prompt(sub_query, today.isoformat(), json.dumps(snapshot, default=str))
        try:
            result = hr_manager_agent.kickoff(prompt, response_format=WorkloadResponse)
        except Exception:
            logger.exception("hr crew failed")
            return (
                "Sorry, I had trouble handling that workload request — "
                "could you rephrase it?"
            )

        response: WorkloadResponse | None = getattr(result, "pydantic", None)
        if response is None:
            logger.warning("hr crew did not return structured output; using raw text")
            return result.raw

        if response.needs_reply:
            # Mirrors crews/document's escalation gate: built, but not fully
            # wired into OrchestratorState yet — see crews/hr/README.md's
            # "Known limitations".
            self.state.pending_actions.append(f"hr: {response.message}")
        return response.message

    @listen("proceed")
    def route_finance(self):
        if "finance" in self.state.routing_decision.get("specialists", []):
            sub_query = _rephrased_query_for(
                self.state.routing_decision, "finance", self.state.user_input
            )
            output = placeholders.run_finance(sub_query)
            self.state.active_agent_outputs["finance"] = output
            self.state.invoked_specialists.append("finance")
            logger.info("finance crew invoked: %s", _truncate(output))

    @listen("proceed")
    def route_document(self):
        if "document" in self.state.routing_decision.get("specialists", []):
            sub_query = _rephrased_query_for(
                self.state.routing_decision, "document", self.state.user_input
            )
            output = self._run_document_team(sub_query)
            self.state.active_agent_outputs["document"] = output
            self.state.invoked_specialists.append("document")
            logger.info("document crew invoked: %s", _truncate(output))

    def _run_document_team(self, sub_query: str) -> str:
        """The Document Team Lead: decide which specialist applies, then
        dispatch directly to that specialist's standalone Agent. Kept as
        plain Python inside the Flow (not a separate crew/module) since the
        Flow already owns sequencing/branching for every other specialist.

        Company profile / financial assumptions / grant narrative / headcount
        plan are never gathered here — each _dispatch_* method below loads
        its own reference data straight from knowledge/documents/*.json and
        injects it directly into that specialist's prompt.
        """
        prompt = build_document_routing_prompt(sub_query, self.state.business_context)
        try:
            decision: DocumentRoutingDecision = document_team_lead_agent.kickoff(
                prompt, response_format=DocumentRoutingDecision
            ).pydantic
        except Exception:
            logger.exception("document routing failed")
            return (
                "Sorry, I had trouble understanding that document request — "
                "could you rephrase it?"
            )

        # grant_scheme/requested_amount_sgd are per-request choices the LLM
        # may only catch in the turn the owner mentions them; cache whatever
        # it found so a later turn in the grant flow can still fall back to
        # it (mirrors financial_forecast caching in _dispatch_financial).
        if decision.grant_scheme:
            self.state.business_context["grant_scheme"] = decision.grant_scheme
        if decision.requested_amount_sgd:
            self.state.business_context["requested_amount_sgd"] = decision.requested_amount_sgd

        if decision.route_type == "clarify" or decision.specialist is None:
            return decision.clarifying_question or "Could you clarify what document help you need?"
        if decision.specialist == "statutory":
            return self._dispatch_statutory(decision)
        if decision.specialist == "financial":
            return self._dispatch_financial()
        return self._dispatch_grant(decision)

    def _dispatch_statutory(self, decision: DocumentRoutingDecision) -> str:
        try:
            profile = CompanyProfile.model_validate(load_company_profile())
        except ValidationError as exc:
            return _describe_validation_errors(exc)

        profile_json = profile.model_dump_json()
        issues = validate_company_profile.run(profile_json)
        if issues != "OK":
            return issues

        document_types = decision.document_types or ["model_constitution"]
        prompt = build_statutory_render_prompt(document_types, profile_json)
        return statutory_compliance_agent.kickoff(prompt).raw

    def _dispatch_financial(self) -> str:
        """The 3-year forecast is deterministic Python math (generate_financial_forecast
        just does arithmetic), so it's computed directly here rather than asked of the
        LLM — an LLM asked to transcribe 36 months of numbers back out as its own
        answer (or as a tool-call argument to summarize_burn_and_breakeven) reliably
        garbles the JSON once enough conversation history accumulates. The agent's
        only job is the judgment call (flagging implausible assumptions) and prose;
        it never sees or re-emits the raw numbers.

        The caller still needs the full forecast, not just the agent's commentary
        (e.g. a user who asked for a forecast wants all 36 months, not a summary
        paragraph) — so it's appended here in Python, verbatim from the tool's own
        output, rather than trusting the agent to reproduce it.
        """
        assumptions = load_financial_assumptions()
        forecast_json = generate_financial_forecast.run(**assumptions)
        self.state.business_context["financial_forecast"] = json.loads(forecast_json)

        summary = summarize_burn_and_breakeven.run(forecast_json)
        prompt = build_financial_prompt(json.dumps(assumptions), summary)
        commentary = financial_synthesizer_agent.kickoff(prompt).raw

        return f"{commentary}\n\nFull 3-year forecast (FinancialForecast JSON):\n{forecast_json}"

    def _dispatch_grant(self, decision: DocumentRoutingDecision) -> str:
        context = self.state.business_context

        # financial_forecast isn't knowledge-base data itself (it's computed by
        # _dispatch_financial, not loaded from a fixture) — it's cached in state
        # to avoid recomputing it when a grant request follows a financial one
        # in the same session.
        if not context.get("financial_forecast"):
            self._dispatch_financial()

        scheme = decision.grant_scheme or context.get("grant_scheme")
        if not scheme:
            return (
                "Which grant scheme is this for — Startup SG Founder or the "
                "Enterprise Development Grant (EDG)?"
            )

        try:
            profile = CompanyProfile.model_validate(load_company_profile())
        except ValidationError as exc:
            return _describe_validation_errors(exc)
        try:
            headcount = HeadcountPlan.model_validate(load_headcount_plan())
        except ValidationError as exc:
            return _describe_validation_errors(exc)

        try:
            narrative_json = json.dumps(load_grant_narrative(scheme))
        except KeyError:
            return (
                f"Internal error: no grant narrative on file for scheme '{scheme}'. "
                "Valid schemes: startup_sg_founder, enterprise_development_grant."
            )
        narrative_issues = validate_grant_narrative.run(scheme, narrative_json)
        if narrative_issues != "OK":
            return narrative_issues

        requested_amount = decision.requested_amount_sgd or context.get("requested_amount_sgd")
        if not requested_amount:
            return "How much funding (in SGD) are you requesting?"

        prompt = build_grant_prompt(
            scheme,
            profile.model_dump_json(),
            json.dumps(context["financial_forecast"]),
            headcount.model_dump_json(),
            narrative_json,
            requested_amount,
        )
        return grant_strategist_agent.kickoff(prompt).raw

    @listen(and_(route_hr, route_finance, route_document))
    def synthesize_step(self):
        self.state.final_response = orchestrator_agent.synthesize(
            self.state.user_input, self.state.active_agent_outputs
        )
        logger.info("synthesized response: %s", _truncate(self.state.final_response))

    def run_consultant_review(self):
        """Not part of the per-turn chain — invoked on a schedule, not on every user turn."""
        output = placeholders.run_consultant()
        logger.info("consultant review: %s", _truncate(output))
        return output


if __name__ == "__main__":
    OrchestratorFlow().plot("OrchestratorFlow.html")

    sample_questions = [
        "I need to know how many people are on the roster this week, and also "
        "whether we're over budget on the marketing expense",
        "Hey! What can you help me with?",
    ]
    for question in sample_questions:
        OrchestratorFlow().kickoff(inputs={"user_input": question})
