"""
crews/hr/tasks.py
Prompt-text builder for the HR / Workload Manager specialist. Returns a
plain string for Agent.kickoff(...) — no crewai.Task or Crew object —
mirroring crews/document/tasks.py: dispatch and sequencing are handled by
OrchestratorFlow (flows/orchestrator_flow.py), and hr_manager_agent is a
standalone Agent invoked directly, not coordinated through a Crew.

The procedure text below is ported verbatim from the standalone prototype's
crew.jsonc `handle_request` task description — it is written as an ordered
procedure on purpose, because the agent follows an explicit list far more
reliably than a description of a goal.
"""
from __future__ import annotations


def build_hr_prompt(sub_query: str, today: str) -> str:
    return (
        "Handle this request from the founder about team workload:\n\n"
        f"{sub_query}\n\n"
        f"Today is {today}.\n\n"
        "Follow this procedure:\n\n"
        "1. Never answer from memory or assumption. Read the ledger first "
        "using your tools — get_team_roster, get_person_workload, "
        "list_open_tasks or get_capacity_forecast, whichever fits the "
        "question.\n\n"
        "2. If the founder is asking a question about load or capacity, "
        "answer it directly from what the tools returned. Quote real "
        "numbers: hours and percentages, not vague words like 'busy'.\n\n"
        "3. If the founder wants work placed on someone, first decide who "
        "you would propose and why, weighing skill fit against current "
        "load, the deadline, and fairness over the last few weeks. Then you "
        "MUST call check_assignment_safety for that person before doing "
        "anything else.\n\n"
        "4. If the verdict is OK, call assign_task and confirm what you "
        "did.\n\n"
        "5. If the verdict is WARN, do NOT assign. Report the warning with "
        "its reason and ask the founder to confirm.\n\n"
        "6. If the verdict is BLOCK, do NOT assign, and do not look for a "
        "way around it. State the reason plainly and propose at least one "
        "alternative — a different person with capacity, or a later date "
        "that would clear.\n\n"
        "7. If the request is about someone's performance, attitude, or "
        "worth as an employee, decline it. You track hours, skills and "
        "dates. You do not rate people.\n\n"
        "8. If a person named in the request is not in the ledger, say so "
        "and list who is, rather than guessing at who was meant.\n\n"
        "Expected output: a WorkloadResponse. Set `kind` to allocation, "
        "status, logged or declined. `message` is what the founder actually "
        "reads — plain sentences, no markdown headers, under 80 words, "
        "suitable for a phone screen. When you placed or refused work, fill "
        "`allocation` including the verdict and its reason. When you "
        "reported load, fill `status`. Set `needs_reply` to true only when "
        "you are waiting on a yes/no from the founder."
    )
