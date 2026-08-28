import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "Config"
SRC_DIR = ROOT_DIR / "src"

for dir in [CONFIG_DIR, ROOT_DIR, SRC_DIR]:
    print(dir)