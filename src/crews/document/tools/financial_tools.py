"""
crews/tools/financial_tools.py
Deterministic financial calculations. These are plain functions wrapped as
CrewAI tools — the LLM supplies assumptions (growth rate, starting revenue,
cost ratios) via the tool's arguments, but the arithmetic itself is Python,
not model output. This is what makes the numbers auditable.
"""
from __future__ import annotations

import sys
from pathlib import Path

from crewai.tools import tool

# Makes `Config` (and, via it, `src`) importable so this file works both as a
# package import and as a direct `python .../financial_tools.py` run.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from Config.config import SRC_DIR  # noqa: E402

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from models import FinancialForecast, MonthlyFinancials  # noqa: E402


def _build_forecast(
    starting_monthly_revenue_sgd: float,
    monthly_revenue_growth_pct: float,
    cogs_pct_of_revenue: float,
    fixed_monthly_opex_sgd: float,
    starting_cash_sgd: float,
    months: int = 36,
) -> FinancialForecast:
    rows: list[MonthlyFinancials] = []
    cash = starting_cash_sgd
    revenue = starting_monthly_revenue_sgd
    break_even_month: int | None = None
    for m in range(1, months + 1):
        cogs = revenue * cogs_pct_of_revenue
        opex = fixed_monthly_opex_sgd
        cash_in = revenue
        cash_out = cogs + opex
        cash += cash_in - cash_out
        rows.append(
            MonthlyFinancials(
                month_index=m,
                revenue_sgd=round(revenue, 2),
                cogs_sgd=round(cogs, 2),
                opex_sgd=round(opex, 2),
                cash_in_sgd=round(cash_in, 2),
                cash_out_sgd=round(cash_out, 2),
                closing_cash_sgd=round(cash, 2),
            )
        )
        if break_even_month is None and (revenue - cogs - opex) >= 0:
            break_even_month = m
        revenue *= 1 + monthly_revenue_growth_pct
    # Burn rate: average monthly net cash outflow over months still burning
    burning_months = [r for r in rows if (r.cash_in_sgd - r.cash_out_sgd) < 0]
    if burning_months:
        burn_rate = sum(
            r.cash_out_sgd - r.cash_in_sgd for r in burning_months
        ) / len(burning_months)
    else:
        burn_rate = 0.0
    runway = starting_cash_sgd / burn_rate if burn_rate > 0 else float("inf")
    return FinancialForecast(
        months=rows,
        monthly_burn_rate_sgd=round(burn_rate, 2),
        runway_months=round(runway, 1) if runway != float("inf") else -1,
        break_even_month_index=break_even_month,
        assumptions={
            "starting_monthly_revenue_sgd": str(starting_monthly_revenue_sgd),
            "monthly_revenue_growth_pct": str(monthly_revenue_growth_pct),
            "cogs_pct_of_revenue": str(cogs_pct_of_revenue),
            "fixed_monthly_opex_sgd": str(fixed_monthly_opex_sgd),
            "starting_cash_sgd": str(starting_cash_sgd),
        },
    )


@tool("Generate 3-Year Cash Flow / P&L Forecast")
def generate_financial_forecast(
    starting_monthly_revenue_sgd: float,
    monthly_revenue_growth_pct: float,
    cogs_pct_of_revenue: float,
    fixed_monthly_opex_sgd: float,
    starting_cash_sgd: float,
) -> str:
    """
    Build a 36-month cash flow / P&L forecast from a small set of assumptions
    and return it as JSON (a FinancialForecast). Use this before compiling
    any grant package or IRAS invoice schema — those depend on this output.
    Args:
        starting_monthly_revenue_sgd: Month-1 revenue in SGD.
        monthly_revenue_growth_pct: Month-over-month growth, e.g. 0.08 for 8%.
        cogs_pct_of_revenue: Cost of goods sold as a fraction of revenue, e.g. 0.35.
        fixed_monthly_opex_sgd: Fixed operating expenses per month (rent, salaries not
            already in headcount, tools, etc).
        starting_cash_sgd: Cash on hand at month 1 (e.g. paid-up capital + prior funding).
    """
    forecast = _build_forecast(
        starting_monthly_revenue_sgd,
        monthly_revenue_growth_pct,
        cogs_pct_of_revenue,
        fixed_monthly_opex_sgd,
        starting_cash_sgd,
    )
    return forecast.model_dump_json(indent=2)


@tool("Compute Break-Even and Burn Rate Summary")
def summarize_burn_and_breakeven(financial_forecast_json: str) -> str:
    """
    Given a FinancialForecast JSON string (from generate_financial_forecast),
    return a short human-readable summary of burn rate, runway, and break-even
    timing, suitable for inserting into a grant narrative.
    Args:
        financial_forecast_json: JSON string of a FinancialForecast object.
    """
    forecast = FinancialForecast.model_validate_json(financial_forecast_json)
    be = (
        f"month {forecast.break_even_month_index}"
        if forecast.break_even_month_index
        else "not reached within 36 months"
    )
    runway = (
        "infinite (cash-flow positive)"
        if forecast.runway_months < 0
        else f"{forecast.runway_months} months"
    )
    return (
        f"Monthly burn rate: SGD {forecast.monthly_burn_rate_sgd:,.2f}. "
        f"Runway: {runway}. Break-even: {be}. "
        f"3-year cumulative revenue: SGD {forecast.three_year_revenue_total:,.2f}."
    )
