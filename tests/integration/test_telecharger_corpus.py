"""Test d'integration : scripts/telecharger_corpus.py.

Skippe automatiquement si le dataset Hugging Face n'est pas present
sur la machine (un dev qui clone n'a pas les 700 Mo).
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from beaume.config import paths


DATASET_LEGI = paths.LEGAL / "legi_2025"


pytestmark = pytest.mark.skipif(
    not DATASET_LEGI.is_dir(),
    reason=f"Dataset HF absent : {DATASET_LEGI}",
)


def _compter_articles(chemin_db: Path) -> int:
    conn = sqlite3.connect(chemin_db)
    try:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    finally:
        conn.close()


def test_telecharger_corpus_limite(tmp_path: Path) -> None:
    """Le script produit une base SQLite avec le nombre d'articles demande."""
    chemin_db = tmp_path / "test.sqlite"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/telecharger_corpus.py",
            "--base", str(chemin_db),
            "--limite", "50",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"Script echoue.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert chemin_db.exists(), "La base SQLite n'a pas ete creee."
    assert _compter_articles(chemin_db) == 50


def test_telecharger_corpus_idempotent(tmp_path: Path) -> None:
    """Relancer le script sur une base existante ne la reconstruit pas."""
    chemin_db = tmp_path / "test.sqlite"
    chemin_db.write_bytes(b"placeholder")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/telecharger_corpus.py",
            "--base", str(chemin_db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "deja presente" in result.stdout
    # La base placeholder doit etre intacte (pas reconstruite).
    assert chemin_db.read_bytes() == b"placeholder"
