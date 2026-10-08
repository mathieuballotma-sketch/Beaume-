"""Tests de l'ontologie juridique."""
from datetime import date
import pytest
from pydantic import ValidationError

from beaume.legal.ids import IdentifiantLegifrance, TypeIdentifiant
from beaume.legal.model import (
    Article,
    Citation,
    CodeJuridique,
    ResultatVerification,
    StatutVerification,
    StatutVersion,
    VersionArticle,
)


def test_identifiant_valide():
    i = IdentifiantLegifrance(valeur="LEGIARTI000006900898")
    assert i.type == TypeIdentifiant.ARTICLE


def test_identifiant_invalide_rejette():
    with pytest.raises(ValidationError):
        IdentifiantLegifrance(valeur="L. 1234-1")


def test_identifiant_prefixe_inconnu_rejette():
    with pytest.raises(ValidationError):
        IdentifiantLegifrance(valeur="FOOBAR000000000001")


def _v(debut: date, fin: date | None, statut=StatutVersion.EN_VIGUEUR):
    return VersionArticle(
        article_id=IdentifiantLegifrance(valeur="LEGIARTI000006900898"),
        numero="L. 1234-1",
        date_debut=debut,
        date_fin=fin,
        texte="Le contrat de travail a duree indeterminee peut...",
        statut=statut,
        source="legifrance",
    )


def test_version_en_vigueur_avant_debut():
    v = _v(date(2020, 1, 1), None)
    assert v.est_en_vigueur_a(date(2019, 12, 31)) is False


def test_version_en_vigueur_dans_intervalle():
    v = _v(date(2020, 1, 1), date(2022, 12, 31))
    assert v.est_en_vigueur_a(date(2021, 6, 15)) is True


def test_version_en_vigueur_apres_fin():
    v = _v(date(2020, 1, 1), date(2022, 12, 31))
    assert v.est_en_vigueur_a(date(2023, 1, 1)) is False


def test_version_sans_fin_reste_en_vigueur():
    v = _v(date(2020, 1, 1), None)
    assert v.est_en_vigueur_a(date(2099, 1, 1)) is True


def test_article_trouve_version_correcte():
    art = Article(
        id=IdentifiantLegifrance(valeur="LEGIARTI000006900898"),
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L. 1234-1",
        versions=[
            _v(date(2016, 1, 1), date(2019, 12, 31)),
            _v(date(2020, 1, 1), None),
        ],
    )
    v = art.version_a(date(2018, 5, 1))
    assert v is not None
    assert v.date_debut == date(2016, 1, 1)


def test_article_aucune_version_sur_plage():
    art = Article(
        id=IdentifiantLegifrance(valeur="LEGIARTI000006900898"),
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L. 1234-1",
        versions=[_v(date(2020, 1, 1), None)],
    )
    assert art.version_a(date(1990, 1, 1)) is None


def test_version_immutable():
    v = _v(date(2020, 1, 1), None)
    with pytest.raises(ValidationError):
        v.texte = "autre texte"  # type: ignore


def test_citation_sans_date_refusee():
    with pytest.raises(ValidationError):
        Citation(code=CodeJuridique.CODE_TRAVAIL, numero="L. 1234-1")  # type: ignore


def test_citation_code_inconnu_refuse():
    with pytest.raises(ValidationError):
        Citation(
            code="code_inexistant",  # type: ignore
            numero="L. 1234-1",
            date_reference=date(2023, 3, 15),
        )


def test_resultat_valide():
    c = Citation(
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L. 1234-1",
        date_reference=date(2023, 3, 15),
    )
    r = ResultatVerification(statut=StatutVerification.VALIDE, citation=c)
    assert r.est_valide is True


def test_resultat_non_valide():
    c = Citation(
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L. 1234-1",
        date_reference=date(2023, 3, 15),
    )
    r = ResultatVerification(statut=StatutVerification.ABROGE, citation=c)
    assert r.est_valide is False
