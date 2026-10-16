"""Verifie que la date de reference est propagee au depot d'articles."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from beaume.application.analyse_dossier import AnalyseDossier


def test_enrichir_articles_utilise_date_reference():
    depot = MagicMock()
    depot.trouver_par_id.return_value = None

    analyseur = AnalyseDossier(
        registre=MagicMock(),
        chercheur=MagicMock(),
        generateur=MagicMock(),
        depot=depot,
    )

    resultat = MagicMock()
    resultat.article_id = "L1234-1"

    date_ref = date(2024, 5, 15)
    analyseur._enrichir_articles([resultat], date_ref)

    depot.trouver_par_id.assert_called_once_with("L1234-1", date_ref)