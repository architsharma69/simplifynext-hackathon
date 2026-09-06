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
    GrantPackage,
    HeadcountPlan,
    RenderedDocument,
)
from crews.document.tasks import (
    build_document_routing_prompt,
    build_financial_summary_prompt,
    build_grant_summary_prompt,
    build_statutory_summary_prompt,
)
from crews.document.tools.financial_tools import (
    generate_financial_forecast,
    summarize_burn_and_breakeven,
)
from crews.document.tools.grant_tools import compile_grant_package, validate_grant_narrative
from crews.document.tools.statutory_tools import render_acra_document, validate_company_profile
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

        # render_acra_document is deterministic and called directly here —
        # not handed to the agent as a tool — so there's no risk of the LLM
        # inventing the wrong arguments for it (see crews/document/agents.py).
        document_types = decision.document_types or ["model_constitution"]
        rendered_jsons = []
        errors = []
        for document_type in document_types:
            result = render_acra_document.run(document_type, profile_json)
            try:
                rendered = RenderedDocument.model_validate_json(result)
            except (ValidationError, ValueError):
                errors.append(result)
                continue
            self.state.generated_documents.append(
                {
                    "document_type": rendered.document_type.value,
                    "filename": Path(rendered.file_path).name,
                    "file_path": rendered.file_path,
                }
            )
            rendered_jsons.append(result)

        if not rendered_jsons:
            return "Couldn't render the requested document(s): " + "; ".join(errors)

        prompt = build_statutory_summary_prompt(document_types, rendered_jsons)
        raw = statutory_compliance_agent.kickoff(prompt).raw
        if errors:
            raw += "\n\nNote: " + "; ".join(errors)
        return raw

    def _dispatch_financial(self) -> str:
        # generate_financial_forecast/summarize_burn_and_breakeven are
        # deterministic and called directly here — not handed to the agent
        # as tools — so there's no risk of the LLM inventing the wrong
        # arguments for them (see crews/document/agents.py).
        assumptions = load_financial_assumptions()
        forecast_json = generate_financial_forecast.run(
            assumptions["starting_monthly_revenue_sgd"],
            assumptions["monthly_revenue_growth_pct"],
            assumptions["cogs_pct_of_revenue"],
            assumptions["fixed_monthly_opex_sgd"],
            assumptions["starting_cash_sgd"],
        )
        try:
            FinancialForecast.model_validate_json(forecast_json)
        except (ValidationError, ValueError):
            logger.exception("generate_financial_forecast returned an invalid FinancialForecast")
            return "Internal error: could not generate a financial forecast from the knowledge-base assumptions."

        self.state.business_context["financial_forecast"] = json.loads(forecast_json)
        burn_summary = summarize_burn_and_breakeven.run(forecast_json)

        prompt = build_financial_summary_prompt(forecast_json, burn_summary)
        return financial_synthesizer_agent.kickoff(prompt).raw

    def _dispatch_grant(self, decision: DocumentRoutingDecision) -> str:
        context = self.state.business_context

        # financial_forecast isn't knowledge-base data itself (it's the
        # Financial Synthesizer's own output) — it's cached in state to avoid
        # re-running that agent when a grant request follows a financial one
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

        narrative_json = json.dumps(load_grant_narrative())
        narrative_issues = validate_grant_narrative.run(scheme, narrative_json)
        if narrative_issues != "OK":
            return narrative_issues

        requested_amount = decision.requested_amount_sgd or context.get("requested_amount_sgd")
        if not requested_amount:
            return "How much funding (in SGD) are you requesting?"

        # compile_grant_package is deterministic and called directly here —
        # not handed to the agent as a tool — so there's no risk of the LLM
        # inventing the wrong arguments for it (see crews/document/agents.py).
        package_json = compile_grant_package.run(
            scheme,
            profile.model_dump_json(),
            json.dumps(context["financial_forecast"]),
            headcount.model_dump_json(),
            narrative_json,
            requested_amount,
        )
        try:
            package = GrantPackage.model_validate_json(package_json)
        except (ValidationError, ValueError):
            logger.exception("compile_grant_package returned an invalid GrantPackage")
            return "Internal error: could not compile the grant package."

        if package.generated_document_path:
            self.state.generated_documents.append(
                {
                    "document_type": f"grant_package_{package.scheme.value}",
                    "filename": Path(package.generated_document_path).name,
                    "file_path": package.generated_document_path,
                }
            )

        prompt = build_grant_summary_prompt(package_json)
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

    # sample_questions = [
    #     "I need to know how many people are on the roster this week, and also "
    #     "whether we're over budget on the marketing expense",
    #     "Hey! What can you help me with?",
    # ]
    # for question in sample_questions:
    #     OrchestratorFlow().kickoff(inputs={"user_input": question})
