import os

import pytest

from crews.orchestrator.agent import route

API_KEY = os.getenv("OPENAI_API_KEY")


@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY not set in .env")
def test_pure_hr_query_delegates_to_hr():
    decision = route("How many employees are on the roster?", {})

    assert decision.route_type == "delegate"
    assert decision.specialists == ["hr"]


@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY not set in .env")
def test_pure_finance_query_delegates_to_finance():
    decision = route("What's our budget for this expense?", {})

    assert decision.route_type == "delegate"
    assert decision.specialists == ["finance"]


@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY not set in .env")
def test_mixed_query_delegates_to_both():
    decision = route(
        "I need to update our employee roster and also check our finance budget for this quarter",
        {},
    )

    assert decision.route_type == "delegate"
    assert set(decision.specialists) == {"hr", "finance"}


@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY not set in .env")
def test_small_talk_is_answered_directly():
    decision = route("Hi there, how are you?", {})

    assert decision.route_type == "direct"
    assert decision.direct_answer


@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY not set in .env")
def test_ambiguous_query_asks_for_clarification():
    decision = route("help", {})

    assert decision.route_type == "clarify"
    assert decision.clarifying_question
