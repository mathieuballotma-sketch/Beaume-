"""Tests du port DepotArticles et de l'adaptateur DepotSQLite."""
from datetime import date
import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)
from beaume.ports.depot_articles import DepotArticles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _version(
    article_id: str,
    numero: str,
    debut: date,
    fin: date | None,
    texte: str,
    statut: StatutVersion = StatutVersion.EN_VIGUEUR,
) -> VersionArticle:
    return VersionArticle(
        article_id=IdentifiantLegifrance(valeur=article_id),
        numero=numero,
        date_debut=debut,
        date_fin=fin,
        texte=texte,
        statut=statut,
        source="legifrance",
    )


def _article_travail(avec_deux_versions: bool = False) -> Article:
    """Article L. 1234-1 du Code du travail, 1 ou 2 versions."""
    id_ = "LEGIARTI000006900898"
    versions = [
        _version(
            id_, "L. 1234-1",
            date(2016, 8, 10), None,
            "Le contrat de travail a duree indeterminee peut toujours "
            "cesser par la volonte d'une des parties contractantes.",
        ),
    ]
    if avec_deux_versions:
        versions.insert(0, _version(
            id_, "L. 1234-1",
            date(2008, 6, 26), date(2016, 8, 9),
            "Ancienne version du texte de l'article L. 1234-1.",
            statut=StatutVersion.ABROGE,
        ))
    return Article(
        id=IdentifiantLegifrance(valeur=id_),
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L. 1234-1",
        versions=versions,
    )


def _article_civil() -> Article:
    id_ = "LEGIARTI000033020517"
    return Article(
        id=IdentifiantLegifrance(valeur=id_),
        code=CodeJuridique.CODE_CIVIL,
        numero="1240",
        versions=[_version(
            id_, "1240",
            date(2016, 10, 1), None,
            "Tout fait quelconque de l'homme qui cause a autrui un "
            "dommage oblige celui par la faute duquel il est arrive "
            "a le reparer.",
        )],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_depot_respecte_contrat(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    assert isinstance(d, DepotArticles)


def test_depot_vide(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    assert d.compter() == 0


def test_enregistrer_un_article(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail()])
    assert d.compter() == 1


def test_enregistrer_deux_articles(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail(), _article_civil()])
    assert d.compter() == 2


def test_enregistrer_idempotent(tmp_path):
    """Enregistrer 2 fois le meme article ne cree pas de doublon."""
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail()])
    d.enregistrer([_article_travail()])
    assert d.compter() == 1


def test_trouver_article_present(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail()])
    res = d.trouver(
        CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(2020, 1, 1),
    )
    assert res is not None
    article, version = res
    assert article.code == CodeJuridique.CODE_TRAVAIL
    assert version.numero == "L. 1234-1"
    assert "contrat de travail" in version.texte


def test_trouver_article_absent_retourne_none(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail()])
    res = d.trouver(
        CodeJuridique.CODE_TRAVAIL, "L. 9999-1", date(2020, 1, 1),
    )
    assert res is None


def test_trouver_avant_premiere_version(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail()])
    res = d.trouver(
        CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(1990, 1, 1),
    )
    assert res is None


def test_trouver_avec_deux_versions(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail(avec_deux_versions=True)])

    # En 2012 : ancienne version
    res_vieille = d.trouver(
        CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(2012, 1, 1),
    )
    assert res_vieille is not None
    _, version_2012 = res_vieille
    assert "Ancienne version" in version_2012.texte
    assert version_2012.statut == StatutVersion.ABROGE

    # En 2020 : version en vigueur
    res_recente = d.trouver(
        CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(2020, 1, 1),
    )
    assert res_recente is not None
    _, version_2020 = res_recente
    assert "peut toujours cesser" in version_2020.texte
    assert version_2020.statut == StatutVersion.EN_VIGUEUR


def test_recherche_texte_simple(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail(), _article_civil()])
    res = d.rechercher_texte("dommage", limite=5)
    assert len(res) == 1
    assert res[0].numero == "1240"


def test_recherche_texte_ignore_accents(tmp_path):
    """La recherche 'reparer' doit trouver 'reparer' meme si ecrit
    differemment ou avec accent."""
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_civil()])
    res = d.rechercher_texte("reparer", limite=5)
    assert len(res) == 1


def test_recherche_texte_sans_resultat(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail()])
    res = d.rechercher_texte("avion helicoptere", limite=5)
    assert res == []


def test_recherche_texte_vide(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail()])
    assert d.rechercher_texte("") == []
    assert d.rechercher_texte("   ") == []


def test_recherche_limite_invalide(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    with pytest.raises(ValueError):
        d.rechercher_texte("contrat", limite=0)


def test_vider(tmp_path):
    d = DepotSQLite(tmp_path / "legi.sqlite")
    d.enregistrer([_article_travail()])
    d.vider()
    assert d.compter() == 0
    assert d.rechercher_texte("contrat") == []


def test_persistance_sur_disque(tmp_path):
    chemin = tmp_path / "legi.sqlite"
    d1 = DepotSQLite(chemin)
    d1.enregistrer([_article_travail()])

    # Nouvelle instance, meme fichier
    d2 = DepotSQLite(chemin)
    assert d2.compter() == 1
    res = d2.trouver(
        CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(2020, 1, 1),
    )
    assert res is not None