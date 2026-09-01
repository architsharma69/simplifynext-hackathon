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

from flows import placeholders
from flows.state import OrchestratorState

logger = logging.getLogger(__name__)


def _truncate(value: str, length: int = 120) -> str:
    return value if len(value) <= length else value[:length] + "..."


@persist()
class OrchestratorFlow(Flow[OrchestratorState]):
    @start()
    def receive_input(self):
        logger.info("received input: %s", _truncate(self.state.user_input))

    @listen(receive_input)
    def classify_intent_step(self):
        self.state.routing_decision = placeholders.classify_intent(self.state.user_input)
        logger.info("routing decision: %s", self.state.routing_decision)

    @router(classify_intent_step)
    def check_confidence(self):
        if self.state.routing_decision.get("needs_clarification"):
            return "clarify"
        return "proceed"

    @listen("clarify")
    def ask_clarification(self):
        self.state.final_response = self.state.routing_decision.get("clarifying_question", "")
        logger.info("asking clarification: %s", self.state.final_response)

    @listen("proceed")
    def route_hr(self):
        if "hr" in self.state.routing_decision.get("specialists", []):
            output = placeholders.run_hr(self.state.user_input)
            self.state.active_agent_outputs["hr"] = output
            self.state.invoked_specialists.append("hr")
            logger.info("hr crew invoked: %s", _truncate(output))

    @listen("proceed")
    def route_finance(self):
        if "finance" in self.state.routing_decision.get("specialists", []):
            output = placeholders.run_finance(self.state.user_input)
            self.state.active_agent_outputs["finance"] = output
            self.state.invoked_specialists.append("finance")
            logger.info("finance crew invoked: %s", _truncate(output))

    @listen("proceed")
    def route_document(self):
        if "document" in self.state.routing_decision.get("specialists", []):
            output = placeholders.run_document(self.state.user_input)
            self.state.active_agent_outputs["document"] = output
            self.state.invoked_specialists.append("document")
            logger.info("document crew invoked: %s", _truncate(output))

    @listen(and_(route_hr, route_finance, route_document))
    def synthesize_step(self):
        self.state.final_response = placeholders.synthesize(self.state.active_agent_outputs)
        logger.info("synthesized response: %s", _truncate(self.state.final_response))

    def run_consultant_review(self):
        """Not part of the per-turn chain — invoked on a schedule, not on every user turn."""
        output = placeholders.run_consultant()
        logger.info("consultant review: %s", _truncate(output))
        return output


if __name__ == "__main__":
    OrchestratorFlow().plot("OrchestratorFlow.html")
