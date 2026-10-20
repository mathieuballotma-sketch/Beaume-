"""Verifie que la date de reference est propagee au depot d'articles."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from beaume.application.analyse_dossier import AnalyseDossier
from beaume.ports.depot_articles import ResultatRechercheArticle


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
    analyseur._enrichir_articles([[resultat]], date_ref)

    depot.trouver_par_id.assert_called_once_with("L1234-1", date_ref)


def test_enrichir_articles_agrege_les_rangs_et_borne_le_nombre_de_candidats():
    id_repetee = "LEGIARTI000000000001"
    id_unique = "LEGIARTI000000000002"

    class Depot:
        def trouver_par_id(self, article_id, date_reference):
            return SimpleNamespace(
                id=SimpleNamespace(valeur=article_id),
                version_a=lambda d: object(),
            )

    analyseur = AnalyseDossier(
        registre=MagicMock(),
        chercheur=MagicMock(),
        generateur=MagicMock(),
        depot=Depot(),
        limite_candidats=1,
    )
    hit_repetee = ResultatRechercheArticle(
        article_id=id_repetee,
        code="code_travail",
        numero="L1",
        extrait="",
        score=0.1,
    )
    hit_unique = ResultatRechercheArticle(
        article_id=id_unique,
        code="code_travail",
        numero="L2",
        extrait="",
        score=100.0,
    )

    articles = analyseur._enrichir_articles(
        [[hit_unique, hit_repetee], [hit_repetee]],
        date(2024, 1, 1),
    )

    assert len(articles) == 1
    assert articles[0].id.valeur == id_repetee
