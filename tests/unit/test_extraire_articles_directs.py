"""Tests de _extraire_articles_directs et _trouver_code_dans_contexte.

Couvre les reproductions de l'audit du 2026-10-22 :
  - L.137-2 ne doit pas devenir 137-2 (prefixe preserve) ;
  - une annee seule (2010) n'est pas un article ;
  - « code de procedure civile » ne doit pas etre lu comme « code civil » ;
  - PROVENANCE_INSUFFISANTE reste une mention non resolue, jamais un
    candidat injecte ;
  - sans code dans le contexte, la reference n'est pas devinee.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from beaume.application.analyse_dossier import (
    AnalyseDossier,
    _trouver_code_dans_contexte,
)
from beaume.legal.model import CodeJuridique
from beaume.ports.resolveur_articles import ResolutionArticle, StatutResolution


DATE_REF = date(2020, 1, 1)


# ---------------------------------------------------------------------------
# Faux depot
# ---------------------------------------------------------------------------

class _FauxDepot:
    """Depot minimal : enregistre les appels, retourne des resolutions fixees."""

    def __init__(self, reponses=None, articles=None):
        # reponses : dict[(CodeJuridique, numero_normalise)] -> ResolutionArticle
        self.reponses = reponses or {}
        # articles : dict[article_id_famille] -> Article (mock)
        self.articles = articles or {}
        self.appels = []

    def resoudre_article(self, code, numero, date_reference, *, strict=True):
        self.appels.append((code, numero, date_reference, strict))
        return self.reponses.get(
            (code, numero),
            ResolutionArticle(
                statut=StatutResolution.REFERENCE_ABSENTE,
                message="absent du faux depot",
            ),
        )

    def trouver_par_id(self, article_id, date_reference):
        return self.articles.get(article_id)


class _FauxDepotSansResolution:
    """Depot sans resoudre_article : verifie la degradation propre."""

    def trouver_par_id(self, article_id, date_reference):
        return None


def _instancier(depot):
    """Construit AnalyseDossier sans passer par __init__ (qui exige
    registre, chercheur, generateur)."""
    obj = AnalyseDossier.__new__(AnalyseDossier)
    obj.depot = depot
    obj.limite_candidats = 10
    obj.limite_articles = 10
    return obj


def _article_mock(article_id):
    a = MagicMock()
    a.id.valeur = article_id
    a.version_a.return_value = MagicMock()
    return a


def _resolution_unique(article_id_famille, code, numero_normalise):
    return ResolutionArticle(
        statut=StatutResolution.UNIQUE,
        article_id_famille=article_id_famille,
        code=code,
        numero_normalise=numero_normalise,
    )


def _resolution_provenance_insuffisante(article_id_famille, code, numero_normalise):
    return ResolutionArticle(
        statut=StatutResolution.PROVENANCE_INSUFFISANTE,
        article_id_famille=article_id_famille,
        code=code,
        numero_normalise=numero_normalise,
        message="provenance insuffisante (jeu de test)",
    )


# ---------------------------------------------------------------------------
# Reproductions de l'audit
# ---------------------------------------------------------------------------

def test_L_137_2_preserve_le_prefixe():
    """L'audit reprochait que L.137-2 devienne 137-2."""
    res = _resolution_unique(
        "art_conso_137_2", CodeJuridique.CODE_CONSOMMATION, "L137-2"
    )
    depot = _FauxDepot(
        reponses={(CodeJuridique.CODE_CONSOMMATION, "L137-2"): res},
        articles={"art_conso_137_2": _article_mock("art_conso_137_2")},
    )
    obj = _instancier(depot)

    articles, mentions = obj._extraire_articles_directs(
        "Vu les articles L.137-2 du Code de la consommation.", DATE_REF
    )

    assert len(articles) == 1
    assert articles[0].id.valeur == "art_conso_137_2"
    assert mentions == []
    codes_appeles = {a[0] for a in depot.appels}
    numeros_appeles = {a[1] for a in depot.appels}
    assert CodeJuridique.CODE_CONSOMMATION in codes_appeles
    assert "L137-2" in numeros_appeles, f"numeros appeles : {numeros_appeles!r}"
    assert "137-2" not in numeros_appeles


def test_annee_seule_n_est_pas_un_article():
    """L'audit reprochait qu'une annee (2010) devienne un article."""
    depot = _FauxDepot()
    obj = _instancier(depot)

    articles, mentions = obj._extraire_articles_directs(
        "Le prêt a été signé en 2010.", DATE_REF
    )

    assert articles == []
    assert mentions == []
    assert depot.appels == [], f"appels inattendus : {depot.appels!r}"


def test_code_procedure_civile_n_est_pas_code_civil():
    """L'audit reprochait que « procedure civile » matche « civil » d'abord."""
    res = _resolution_unique(
        "art_proc_civile_123",
        CodeJuridique.CODE_PROCEDURE_CIVILE,
        "123",
    )
    depot = _FauxDepot(
        reponses={(CodeJuridique.CODE_PROCEDURE_CIVILE, "123"): res},
        articles={"art_proc_civile_123": _article_mock("art_proc_civile_123")},
    )
    obj = _instancier(depot)

    articles, mentions = obj._extraire_articles_directs(
        "Vu l'article 123 du code de procédure civile.", DATE_REF
    )

    assert len(articles) == 1
    codes_appeles = [a[0] for a in depot.appels]
    assert CodeJuridique.CODE_PROCEDURE_CIVILE in codes_appeles
    assert CodeJuridique.CODE_CIVIL not in codes_appeles


def test_provenance_insuffisante_reste_mention_non_resolue():
    """PROVENANCE_INSUFFISANTE ne doit pas etre injectee comme candidat."""
    res = _resolution_provenance_insuffisante(
        "art_conso_137_2", CodeJuridique.CODE_CONSOMMATION, "L137-2"
    )
    depot = _FauxDepot(
        reponses={(CodeJuridique.CODE_CONSOMMATION, "L137-2"): res},
        articles={"art_conso_137_2": _article_mock("art_conso_137_2")},
    )
    obj = _instancier(depot)

    articles, mentions = obj._extraire_articles_directs(
        "Vu les articles L.137-2 du Code de la consommation.", DATE_REF
    )

    assert articles == []
    assert len(mentions) == 1
    m = mentions[0]
    assert m["statut"] == StatutResolution.PROVENANCE_INSUFFISANTE.value
    assert m["numero_normalise"] == "L137-2"
    assert "provenance insuffisante" in m["motif"].lower()
    assert m["code"] == CodeJuridique.CODE_CONSOMMATION.value


def test_reference_sans_code_contexte_est_mention_non_resolue():
    """Sans code identifiable, la reference n'est pas devinee."""
    depot = _FauxDepot()
    obj = _instancier(depot)

    articles, mentions = obj._extraire_articles_directs(
        "L.137-2 est applicable.", DATE_REF
    )

    assert articles == []
    assert len(mentions) == 1
    assert mentions[0]["statut"] == "code_absent_du_contexte"
    assert mentions[0]["reference_brute"] == "L.137-2"
    assert depot.appels == []


def test_dedup_par_identifiant_article():
    """Deux references au meme article : un seul article resolu."""
    res = _resolution_unique(
        "art_conso_137_2", CodeJuridique.CODE_CONSOMMATION, "L137-2"
    )
    depot = _FauxDepot(
        reponses={(CodeJuridique.CODE_CONSOMMATION, "L137-2"): res},
        articles={"art_conso_137_2": _article_mock("art_conso_137_2")},
    )
    obj = _instancier(depot)

    articles, mentions = obj._extraire_articles_directs(
        "Vu L.137-2 du Code de la consommation. "
        "Voir aussi L.137-2 du Code de la consommation.",
        DATE_REF,
    )

    assert len(articles) == 1
    assert articles[0].id.valeur == "art_conso_137_2"


def test_depot_sans_resoudre_article_ne_casse_pas():
    """Depot sans resoudre_article : retour vide, pas d'exception."""
    obj = _instancier(_FauxDepotSansResolution())

    articles, mentions = obj._extraire_articles_directs(
        "Vu L.137-2 du Code de la consommation.", DATE_REF
    )

    assert articles == []
    assert mentions == []


def test_deux_references_deux_codes():
    """Chaque reference recoit le code de sa clause, pas celui de l'autre."""
    res_conso = _resolution_unique(
        "art_conso", CodeJuridique.CODE_CONSOMMATION, "L137-2"
    )
    res_civil = _resolution_unique("art_civil", CodeJuridique.CODE_CIVIL, "2224")
    depot = _FauxDepot(
        reponses={
            (CodeJuridique.CODE_CONSOMMATION, "L137-2"): res_conso,
            (CodeJuridique.CODE_CIVIL, "2224"): res_civil,
        },
        articles={
            "art_conso": _article_mock("art_conso"),
            "art_civil": _article_mock("art_civil"),
        },
    )
    obj = _instancier(depot)

    articles, mentions = obj._extraire_articles_directs(
        "Vu les articles L.137-2 du Code de la consommation et 2224 du Code civil.",
        DATE_REF,
    )

    assert {a.id.valeur for a in articles} == {"art_conso", "art_civil"}
    assert mentions == []


# ---------------------------------------------------------------------------
# _trouver_code_dans_contexte : tri par longueur et borne de clause.
# ---------------------------------------------------------------------------

def test_code_priorite_longueur_procedure_civile():
    t = "article 123 du code de procédure civile."
    fin = t.index(" du code")
    code = _trouver_code_dans_contexte(t, 0, fin)
    assert code is CodeJuridique.CODE_PROCEDURE_CIVILE


def test_code_priorite_longueur_procedure_penale():
    t = "article 123 du code de procédure pénale."
    fin = t.index(" du code")
    code = _trouver_code_dans_contexte(t, 0, fin)
    assert code is CodeJuridique.CODE_PROCEDURE_PENALE


def test_code_borne_par_et():
    """La clause « et » empeche l'attribution du code de la seconde
    reference a la premiere."""
    t = "L.137-2 du Code de la consommation et 2224 du Code civil."
    pos = t.index("L.137-2")
    fin = pos + len("L.137-2")
    code = _trouver_code_dans_contexte(t, pos, fin)
    assert code is CodeJuridique.CODE_CONSOMMATION