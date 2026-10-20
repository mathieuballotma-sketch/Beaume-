"""Verifie que le rendu Markdown affiche bien l'etat du rapport."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from beaume.legal.analyse import Analyse
from beaume.output.rapport import Rapport, rendre_markdown


def _rapport(analyse: Analyse) -> Rapport:
    return Rapport(
        dossier=Path("/tmp/test"),
        date_reference=date(2024, 1, 1),
        analyse=analyse,
        verifications=[],
        modele_llm="test",
        duree_s=0.0,
    )


def test_rendu_complet_affiche_complet():
    a = Analyse(
        date_reference=date(2024, 1, 1),
        contexte="Un fait.",
    )
    md = rendre_markdown(_rapport(a))
    assert "COMPLET" in md
    assert "PARTIEL" not in md
    assert "ECHEC" not in md


def test_rapport_ne_revele_pas_le_chemin_local_complet():
    md = rendre_markdown(_rapport(Analyse(
        date_reference=date(2024, 1, 1),
        contexte="Un fait.",
    )))

    assert "`test`" in md
    assert "/tmp/" not in md


def test_rendu_partiel_affiche_fichiers_ignores():
    a = Analyse(
        date_reference=date(2024, 1, 1),
        contexte="Un fait.",
        fichiers_ignores=("scan.pdf", "image.jpg"),
    )
    md = rendre_markdown(_rapport(a))
    assert "PARTIEL" in md
    assert "scan.pdf" in md
    assert "image.jpg" in md
    assert "COMPLET" not in md


def test_rendu_partiel_affiche_avertissements():
    a = Analyse(
        date_reference=date(2024, 1, 1),
        contexte="Un fait.",
        avertissements=("Aucun article candidat n'a ete trouve.",),
    )
    md = rendre_markdown(_rapport(a))

    assert "PARTIEL" in md
    assert "Aucun article candidat" in md


def test_rendu_echec_affiche_erreur():
    a = Analyse(
        date_reference=date(2024, 1, 1),
        erreur="Reponse LLM illisible",
    )
    md = rendre_markdown(_rapport(a))
    assert "ECHEC" in md
    assert "Reponse LLM illisible" in md
    assert "COMPLET" not in md
