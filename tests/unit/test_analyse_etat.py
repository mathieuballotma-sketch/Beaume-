"""Verifie que l'etat d'une Analyse reflete bien les erreurs et ignores."""
from __future__ import annotations

from datetime import date

from beaume.legal.analyse import Analyse


def test_analyse_vide_est_echec():
    a = Analyse(date_reference=date(2024, 1, 1))
    assert a.etat == "ECHEC"


def test_analyse_avec_contexte_est_complet():
    a = Analyse(
        date_reference=date(2024, 1, 1),
        contexte="Un fait quelconque.",
    )
    assert a.etat == "COMPLET"


def test_analyse_avec_fichier_ignore_est_partiel():
    a = Analyse(
        date_reference=date(2024, 1, 1),
        contexte="Un fait quelconque.",
        fichiers_ignores=("scan.pdf",),
    )
    assert a.etat == "PARTIEL"


def test_analyse_avec_erreur_est_echec():
    a = Analyse(
        date_reference=date(2024, 1, 1),
        contexte="Un fait quelconque.",
        erreur="Reponse LLM illisible",
    )
    assert a.etat == "ECHEC"


def test_erreur_prime_sur_fichiers_ignores():
    a = Analyse(
        date_reference=date(2024, 1, 1),
        erreur="Reponse LLM illisible",
        fichiers_ignores=("scan.pdf",),
    )
    assert a.etat == "ECHEC"