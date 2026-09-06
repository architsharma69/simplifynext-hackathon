"""
crews/hr/schemas.py
Typed output contract for the HR / Workload Manager crew. This is the object
that moves between hr_manager_agent and OrchestratorFlow — mirrors how
crews/document/schemas.py holds that team's contracts.

Ported from plan/workload_manager/schemas.py unchanged.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Alternative(BaseModel):
    """A different way to get the work done, offered alongside a refusal."""
    person: str = Field(..., description="Name of the person proposed instead")
    reason: str = Field(..., description="Why they're a workable alternative")


class Allocation(BaseModel):
    """The outcome of trying to place one piece of work on one person."""
    task_title: str
    assignee: Optional[str] = Field(
        None, description="None when the assignment was blocked or is unconfirmed"
    )
    est_hours: float
    due_date: str = Field(..., description="ISO date, YYYY-MM-DD")

    verdict: Literal["OK", "WARN", "BLOCK"] = Field(
        ..., description="Straight from check_assignment_safety — never invented"
    )
    verdict_reason: str = Field(
        ..., description="The reason string returned with the verdict"
    )

    rationale: str = Field(
        ..., description="Why this person, in one sentence: the trade-off made"
    )
    alternatives: list[Alternative] = Field(
        default_factory=list,
        description="Required when verdict is BLOCK; at least one option",
    )


class PersonLoad(BaseModel):
    """One person's committed hours against their capacity for one week."""
    name: str
    committed_hours: float
    capacity_hours: float
    load_pct: float = Field(..., description="committed / capacity, e.g. 1.18 for 118%")
    flags: list[str] = Field(
        default_factory=list,
        description="e.g. 'on leave Thu-Fri', 'third overloaded week'",
    )


class TeamStatus(BaseModel):
    """A load snapshot for the whole team, for one week."""
    week: str = Field(..., description="ISO week, e.g. 2026-W36")
    people: list[PersonLoad]
    summary: str = Field(..., description="One sentence a founder can act on")


class BurnoutFlag(BaseModel):
    """Raised by the scheduled scan, not by a conversation."""
    person: str
    weeks_overloaded: int
    peak_load_pct: float
    recommendation: str = Field(
        ..., description="What to actually do about it — reassign what, to whom"
    )


class WorkloadResponse(BaseModel):
    """
    The single shape hr_manager_agent returns for every turn.

    One response model means OrchestratorFlow has one thing to read
    (`.message`) regardless of which branch of the HR procedure ran.
    """
    kind: Literal["allocation", "status", "logged", "declined"]

    message: str = Field(
        ...,
        description="What the founder reads. Plain sentences, under 80 words, "
                    "phone-screen friendly. No markdown headers.",
    )

    allocation: Optional[Allocation] = None
    status: Optional[TeamStatus] = None

    needs_reply: bool = Field(
        False,
        description="True only when waiting on a yes/no from the founder. "
                    "OrchestratorFlow can surface this via pending_actions.",
    )
