"""Test d'integration : scripts/telecharger_corpus.py.

Skippe automatiquement si le dataset Hugging Face n'est pas present
sur la machine (un dev qui clone n'a pas les 700 Mo).
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.config import paths
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)


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


def _mini_base(chemin_db: Path) -> None:
    """Cree une base SQLite exploitable avec 2 articles."""
    depot = DepotSQLite(chemin_db)
    depot.enregistrer([
        _article("LEGIARTI000000000001", CodeJuridique.CODE_CIVIL, "1240"),
        _article("LEGIARTI000000000002", CodeJuridique.CODE_TRAVAIL, "L. 1234-1"),
    ])


def _article(article_id: str, code: CodeJuridique, numero: str) -> Article:
    identifiant = IdentifiantLegifrance(valeur=article_id)
    version = VersionArticle(
        article_id=identifiant,
        numero=numero,
        date_debut=date(2020, 1, 1),
        date_fin=None,
        texte="Texte de test.",
        statut=StatutVersion.EN_VIGUEUR,
        source="test",
    )
    return Article(
        id=identifiant,
        code=code,
        numero=numero,
        versions=[version],
    )


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
    """Relancer le script sur une base existante ne la reconstruit pas.

    Verifie que la base existante reste exploitable : lisible, avec
    ses 2 articles intacts. Un placeholder binaire ne prouverait rien.
    """
    chemin_db = tmp_path / "test.sqlite"
    _mini_base(chemin_db)
    assert _compter_articles(chemin_db) == 2

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

    # La base doit toujours etre lisible et contenir les 2 articles.
    assert _compter_articles(chemin_db) == 2