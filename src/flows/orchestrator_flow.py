import json
import logging
import sys
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
    FinancialForecast,
    HeadcountPlan,
)
from crews.document.tasks import (
    build_document_routing_prompt,
    build_financial_prompt,
    build_grant_prompt,
    build_statutory_render_prompt,
)
from crews.document.tools.grant_tools import validate_grant_narrative
from crews.document.tools.statutory_tools import validate_company_profile
from crews.orchestrator import agent as orchestrator_agent
from flows import placeholders
from flows.state import OrchestratorState

logger = logging.getLogger(__name__)


def _truncate(value: str, length: int = 120) -> str:
    return value if len(value) <= length else value[:length] + "..."


def _rephrased_query_for(routing_decision: dict, specialist: str, fallback: str) -> str:
    for entry in routing_decision.get("rephrased_queries", []):
        if entry.get("specialist") == specialist:
            return entry.get("query", fallback)
    return fallback


_REQUIRED_FINANCIAL_ASSUMPTION_KEYS = [
    "starting_monthly_revenue_sgd",
    "monthly_revenue_growth_pct",
    "cogs_pct_of_revenue",
    "fixed_monthly_opex_sgd",
    "starting_cash_sgd",
]


def _describe_validation_errors(exc: ValidationError) -> str:
    fields = sorted({".".join(str(part) for part in err["loc"]) for err in exc.errors()})
    return "I still need: " + ", ".join(fields) + "."


def _extract_json_blob(raw: str) -> str | None:
    """Best-effort pull of the first {...} JSON object out of raw agent text.

    Agent.kickoff() output is free text that may wrap the JSON payload in
    prose; this is a heuristic, not a parser, until the document specialists
    move to CrewAI's structured `response_format` for their tool outputs too.
    """
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return raw[start : end + 1]


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
            output = placeholders.run_hr(sub_query)
            self.state.active_agent_outputs["hr"] = output
            self.state.invoked_specialists.append("hr")
            logger.info("hr crew invoked: %s", _truncate(output))

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
        """The Document Team Lead: decide which specialist applies, merge any
        newly-extracted facts into business_context, then validate and
        dispatch directly to that specialist's standalone Agent. Kept as
        plain Python inside the Flow (not a separate crew/module) since the
        Flow already owns sequencing/branching for every other specialist.
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

        try:
            extracted = json.loads(decision.extracted_fields_json or "{}")
        except json.JSONDecodeError:
            extracted = {}
        if isinstance(extracted, dict):
            self.state.business_context.update(extracted)

        if decision.route_type == "clarify" or decision.specialist is None:
            return decision.clarifying_question or "Could you clarify what document help you need?"
        if decision.specialist == "statutory":
            return self._dispatch_statutory(decision)
        if decision.specialist == "financial":
            return self._dispatch_financial()
        return self._dispatch_grant(decision)

    def _dispatch_statutory(self, decision: DocumentRoutingDecision) -> str:
        try:
            profile = CompanyProfile.model_validate(
                self.state.business_context.get("company_profile", {})
            )
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
        assumptions = self.state.business_context.get("financial_assumptions", {})
        missing = [k for k in _REQUIRED_FINANCIAL_ASSUMPTION_KEYS if k not in assumptions]
        if missing:
            return "I still need: " + ", ".join(missing) + "."

        prompt = build_financial_prompt(json.dumps(assumptions))
        raw = financial_synthesizer_agent.kickoff(prompt).raw

        blob = _extract_json_blob(raw)
        if blob:
            try:
                forecast = FinancialForecast.model_validate_json(blob)
                self.state.business_context["financial_forecast"] = json.loads(
                    forecast.model_dump_json()
                )
            except (ValidationError, ValueError):
                logger.warning("could not parse a FinancialForecast out of agent output")
        return raw

    def _dispatch_grant(self, decision: DocumentRoutingDecision) -> str:
        context = self.state.business_context

        if not context.get("financial_forecast"):
            if context.get("financial_assumptions"):
                self._dispatch_financial()
            if not context.get("financial_forecast"):
                return (
                    "I still need your financial assumptions (starting monthly "
                    "revenue, growth rate, COGS %, fixed opex, starting cash) "
                    "before I can compile a grant package."
                )

        scheme = decision.grant_scheme or context.get("grant_scheme")
        if not scheme:
            return (
                "Which grant scheme is this for — Startup SG Founder or the "
                "Enterprise Development Grant (EDG)?"
            )

        try:
            profile = CompanyProfile.model_validate(context.get("company_profile", {}))
        except ValidationError as exc:
            return _describe_validation_errors(exc)
        try:
            headcount = HeadcountPlan.model_validate(context.get("headcount_plan", {}))
        except ValidationError as exc:
            return _describe_validation_errors(exc)

        narrative_sections = context.get("narrative_sections", {})
        narrative_json = json.dumps(narrative_sections)
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
