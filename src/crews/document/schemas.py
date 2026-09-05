"""
crews/document/schemas.py
Typed data contracts for the document crew (HERMES). These are the objects
that move between the document specialist agents and OrchestratorFlow.
Agents should populate these via structured tool outputs (Pydantic-validated),
never via freeform prose handed to the next agent.

The Flow-level session state lives in ``flows/state.py`` (OrchestratorState).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EscalationStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class DocumentType(str, Enum):
    MODEL_CONSTITUTION = "model_constitution"
    FORM_45 = "form_45"
    FORM_45B = "form_45b"
    FIRST_BOARD_RESOLUTION = "first_board_resolution"
    RORC_REGISTER = "rorc_register"
    CASH_FLOW_FORECAST = "cash_flow_forecast"
    PL_STATEMENT = "pl_statement"
    IRAS_INVOICE = "iras_invoice"
    GRANT_PACKAGE_STARTUP_SG = "grant_package_startup_sg_founder"
    GRANT_PACKAGE_EDG = "grant_package_edg"


class GrantScheme(str, Enum):
    STARTUP_SG_FOUNDER = "startup_sg_founder"
    EDG = "enterprise_development_grant"


# ---------------------------------------------------------------------------
# Entity / company inputs (collected up-front, referenced by every sub-agent)
# ---------------------------------------------------------------------------


class Director(BaseModel):
    full_name: str
    nric_or_passport: str
    nationality: str
    residential_address: str
    is_resident_director: bool = False


class Shareholder(BaseModel):
    full_name: str
    id_number: str
    shares_held: int
    share_class: str = "Ordinary"


class CompanyProfile(BaseModel):
    proposed_company_name: str
    registered_address: str
    principal_activity_ssic_code: str
    directors: list[Director]
    shareholders: list[Shareholder]
    company_secretary_name: Optional[str] = None
    paid_up_capital_sgd: float


# ---------------------------------------------------------------------------
# Financial Synthesizer outputs
# ---------------------------------------------------------------------------


class MonthlyFinancials(BaseModel):
    month_index: int  # 1..36
    revenue_sgd: float
    cogs_sgd: float
    opex_sgd: float
    cash_in_sgd: float
    cash_out_sgd: float
    closing_cash_sgd: float


class FinancialForecast(BaseModel):
    """Typed handoff from Internal Financial Synthesizer Agent."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    currency: str = "SGD"
    months: list[MonthlyFinancials]
    monthly_burn_rate_sgd: float
    runway_months: float
    break_even_month_index: Optional[int] = None
    assumptions: dict[str, str] = Field(default_factory=dict)

    @property
    def three_year_revenue_total(self) -> float:
        return sum(m.revenue_sgd for m in self.months)


# ---------------------------------------------------------------------------
# HR headcount (produced by the HR crew elsewhere in the system; HERMES only
# consumes it, so it's modeled here as an input contract)
# ---------------------------------------------------------------------------


class HeadcountLine(BaseModel):
    role_title: str
    department: str
    count: int
    monthly_salary_sgd: float
    start_month_index: int


class HeadcountPlan(BaseModel):
    lines: list[HeadcountLine]

    @property
    def total_monthly_payroll_sgd(self) -> float:
        return sum(l.count * l.monthly_salary_sgd for l in self.lines)


# ---------------------------------------------------------------------------
# Grant & Capital Strategist outputs
# ---------------------------------------------------------------------------


class GrantPackage(BaseModel):
    scheme: GrantScheme
    company: CompanyProfile
    financials: FinancialForecast
    headcount: HeadcountPlan
    narrative_sections: dict[str, str]  # e.g. {"problem_statement": "...", "solution": "..."}
    requested_amount_sgd: float
    generated_document_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Generic rendered-document envelope (what every tool ultimately returns)
# ---------------------------------------------------------------------------


class RenderedDocument(BaseModel):
    document_type: DocumentType
    file_path: str
    checksum_sha256: str
    rendered_at: datetime = Field(default_factory=datetime.utcnow)
    source_data_summary: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Human escalation
# ---------------------------------------------------------------------------


class EscalationRequest(BaseModel):
    escalation_id: str
    session_id: str
    document_type: DocumentType
    file_path: str
    reason: str
    status: EscalationStatus = EscalationStatus.PENDING_REVIEW
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None
    reviewer_comment: Optional[str] = None


# ---------------------------------------------------------------------------
# Document Team Lead routing (OrchestratorFlow -> document specialists)
# ---------------------------------------------------------------------------


class DocumentRoutingDecision(BaseModel):
    """The Document Team Lead's decision for one turn of document work.

    No default values, mirroring crews/orchestrator/schemas.py's
    RoutingDecision: every field must be filled in (using []/null for
    whichever don't apply), and open-ended data is passed as a JSON string
    rather than a freeform dict, matching every other Flow<->agent boundary
    in this crew (e.g. render_acra_document's company_profile_json).
    """

    route_type: Literal["dispatch", "clarify"]
    specialist: Literal["statutory", "financial", "grant"] | None
    document_types: list[str]
    grant_scheme: str | None
    requested_amount_sgd: float | None
    extracted_fields_json: str
    clarifying_question: str | None
