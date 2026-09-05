from pathlib import Path

import yaml
from crewai import LLM, Agent

from Config import config

from .schemas import RoutingDecision

_CONFIG_DIR = Path(__file__).resolve().parent / "config"
_AGENTS = yaml.safe_load((_CONFIG_DIR / "agents.yaml").read_text())
_TASKS = yaml.safe_load((_CONFIG_DIR / "tasks.yaml").read_text())


def build_orchestrator_agent() -> Agent:
    cfg = _AGENTS["orchestrator"]
    return Agent(
        role=cfg["role"],
        goal=cfg["goal"],
        backstory=cfg["backstory"],
        llm=LLM(model=config.ORCHESTRATOR_MODEL),
        verbose=True,
    )


def _build_prompt(task_name: str, **kwargs) -> str:
    task = _TASKS[task_name]
    description = task["description"].format(**kwargs)
    return f"{description}\n\nExpected output: {task['expected_output']}"


def route(user_input: str, business_context: dict) -> RoutingDecision:
    prompt = _build_prompt(
        "routing_task", user_input=user_input, business_context=business_context
    )
    output = build_orchestrator_agent().kickoff(prompt, response_format=RoutingDecision)
    return output.pydantic


def synthesize(user_input: str, specialist_outputs: dict[str, str]) -> str:
    prompt = _build_prompt(
        "synthesis_task", user_input=user_input, specialist_outputs=specialist_outputs
    )
    output = build_orchestrator_agent().kickoff(prompt)
    return output.raw
