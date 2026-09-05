import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "Config"
SRC_DIR = ROOT_DIR / "src"

ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "openai/gpt-4o-mini")