"""
test_hr_crew.py
Tests for the HR specialist crew (crews/hr/) and the dispatch logic that
lives in OrchestratorFlow._run_hr_team (flows/orchestrator_flow.py). No LLM
API key needed: hr_manager_agent.kickoff is monkeypatched, mirroring
test_document_crew.py's pattern for the document specialists.
"""
from __future__ import annotations

from crews.hr.schemas import Allocation, WorkloadResponse
from flows.orchestrator_flow import OrchestratorFlow


class _FakeKickoffResult:
    def __init__(self, raw=None, pydantic=None):
        self.raw = raw
        self.pydantic = pydantic


class _FakeAgent:
    """Stands in for crewai's hr_manager_agent. Agent is a pydantic model
    and rejects arbitrary attribute assignment, so tests monkeypatch the
    module-level name orchestrator_flow.py holds rather than `.kickoff` on
    the instance — same pattern test_document_crew.py uses.
    """

    def __init__(self, result):
        self._result = result
        self.calls: list[str] = []

    def kickoff(self, prompt, **kwargs):
        self.calls.append(prompt)
        return self._result


def test_run_hr_team_returns_the_founder_facing_message(monkeypatch):
    response = WorkloadResponse(
        kind="status",
        message="Priya is at 118% this week; everyone else has room.",
        needs_reply=False,
    )
    fake_hr = _FakeAgent(_FakeKickoffResult(pydantic=response))
    monkeypatch.setattr("flows.orchestrator_flow.hr_manager_agent", fake_hr)

    flow = OrchestratorFlow()
    output = flow._run_hr_team("How loaded is the team this week?")

    assert output == "Priya is at 118% this week; everyone else has room."
    assert len(fake_hr.calls) == 1
    assert "How loaded is the team this week?" in fake_hr.calls[0]
    assert flow.state.pending_actions == []


def test_run_hr_team_queues_pending_action_when_needs_reply(monkeypatch):
    response = WorkloadResponse(
        kind="allocation",
        message="Assigning this to Priya would put her at 92% — confirm?",
        allocation=Allocation(
            task_title="New landing page copy",
            assignee=None,
            est_hours=6,
            due_date="2026-09-10",
            verdict="WARN",
            verdict_reason="Priya would be at 92% in 2026-W37.",
            rationale="Best skill fit, but close to capacity.",
        ),
        needs_reply=True,
    )
    fake_hr = _FakeAgent(_FakeKickoffResult(pydantic=response))
    monkeypatch.setattr("flows.orchestrator_flow.hr_manager_agent", fake_hr)

    flow = OrchestratorFlow()
    output = flow._run_hr_team("Put the landing page copy on Priya.")

    assert output == response.message
    assert flow.state.pending_actions == [f"hr: {response.message}"]


def test_run_hr_team_falls_back_to_raw_text_without_structured_output(monkeypatch):
    fake_hr = _FakeAgent(_FakeKickoffResult(raw="Free text answer.", pydantic=None))
    monkeypatch.setattr("flows.orchestrator_flow.hr_manager_agent", fake_hr)

    flow = OrchestratorFlow()
    output = flow._run_hr_team("Who's free this week?")

    assert output == "Free text answer."


def test_run_hr_team_recovers_from_an_exception(monkeypatch):
    class _Raises:
        def kickoff(self, prompt, **kwargs):
            raise RuntimeError("model call failed")

    monkeypatch.setattr("flows.orchestrator_flow.hr_manager_agent", _Raises())

    flow = OrchestratorFlow()
    output = flow._run_hr_team("How loaded is the team?")

    assert "trouble" in output.lower()
