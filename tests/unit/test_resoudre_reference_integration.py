"""Test d'integration : resoudre_reference avec un vrai DepotSQLite.

Couvre le chemin resoudre_reference -> ResolutionArticle -> trouver_par_id,
qui n'etait teste nulle part avant le 21 octobre 2026. Le bug corrige
ce jour-la : resoudre_reference passait une chaine code ("code_civil")
a resoudre_article qui attendait CodeJuridique, provoquant
DONNEES_INCOHERENTES sur toutes les citations.
"""
from datetime import date

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article, CodeJuridique, StatutVersion, VersionArticle,
)


def _article(code: CodeJuridique, numero: str, famille: str,
             version: str, debut: date, fin: date | None = None) -> Article:
    return Article(
        id=IdentifiantLegifrance(valeur=famille),
        code=code,
        numero=numero,
        versions=[VersionArticle(
            article_id=IdentifiantLegifrance(valeur=famille),
            numero=numero,
            date_debut=debut,
            date_fin=fin,
            texte="texte",
            statut=StatutVersion.EN_VIGUEUR,
            source=f"DILA-LEGI:{version}",
        )],
    )


def test_resoudre_reference_avec_chaine_code(tmp_path):
    """resoudre_reference recoit 'code_civil' (str) et doit resoudre."""
    from scripts.resoudre_visa import ReferenceVisa, resoudre_reference

    dep = DepotSQLite(tmp_path / "legi.sqlite")
    dep.enregistrer([_article(
        CodeJuridique.CODE_CIVIL, "1382",
        "LEGIARTI000000000001", "LEGIARTI000000000011",
        date(1804, 3, 21),
    )])

    ref = ReferenceVisa(code="code_civil", numero="1382")
    resultat = resoudre_reference(dep, ref, date(2020, 1, 1))

    assert resultat.article_id == "LEGIARTI000000000001"
    assert resultat.version_legiarti == "LEGIARTI000000000011"
    assert resultat.code == "code_civil"
    assert resultat.numero == "1382"


def test_resoudre_reference_code_inconnu(tmp_path):
    """Un code absent de l'enum CodeJuridique leve VisaInvalide."""
    from scripts.resoudre_visa import ReferenceVisa, VisaInvalide, resoudre_reference

    dep = DepotSQLite(tmp_path / "legi.sqlite")
    ref = ReferenceVisa(code="code_bidon", numero="1")

    try:
        resoudre_reference(dep, ref, date(2020, 1, 1))
        raise AssertionError("aurait du lever VisaInvalide")
    except VisaInvalide:
        pass
