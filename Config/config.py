import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "Config"
SRC_DIR = ROOT_DIR / "src"

ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "openai/gpt-4o-mini")

# Model + API key shared by the document team (document_team_lead_agent plus
# the statutory/financial/grant specialists in crews/document/agents.py).
# DOCUMENT_TEAM_API_KEY is optional — leave it unset to fall back to
# whichever provider-specific env var CrewAI's LLM already resolves on its
# own (e.g. ANTHROPIC_API_KEY for a claude-* model).
DOCUMENT_TEAM_MODEL = os.getenv("DOCUMENT_TEAM_MODEL", "openai/gpt-4o-mini")
DOCUMENT_TEAM_API_KEY = os.getenv("DOCUMENT_TEAM_API_KEY")

# Where rendered documents (ACRA filings, grant packages) are written.
# Override with the HERMES_DOCUMENT_DIR env var if you want them elsewhere.
DOCUMENT_OUTPUT_DIR = Path(
    os.environ.get("HERMES_DOCUMENT_DIR", ROOT_DIR / "output" / "documents")
)
