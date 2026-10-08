"""Chemins du projet Beaume. Source unique de verite."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
INBOX = DATA / "inbox"
OUT = DATA / "out"
LEGAL = DATA / "legal"
VECTOR = DATA / "vector"
LOGS = DATA / "logs"
TMP = DATA / "tmp"

ALL_DATA_DIRS = [INBOX, OUT, LEGAL, VECTOR, LOGS, TMP]


def ensure_dirs() -> None:
    for d in ALL_DATA_DIRS:
        d.mkdir(parents=True, exist_ok=True)
