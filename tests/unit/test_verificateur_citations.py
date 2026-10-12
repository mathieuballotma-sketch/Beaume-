"""Tests du verificateur de citations."""
from datetime import date
from pathlib import Path

import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.legal.model import (
    Citation,
    CodeJuridique,
    StatutVerification,
)
from beaume.ports.verificateur_citations import VerificateurCitations


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"


def _verificateur(tmp_path) -> VerificateurStandard:
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    depot.enregistrer(SourceFichierLocal(FIXTURE).charger())
    return VerificateurStandard(depot)


def _citation(code, numero, d, extrait=None) -> Citation:
    return Citation(
        code=code,
        numero=numero,
        date_reference=d,
        extrait=extrait,
    )


def test_verificateur_respecte_contrat(tmp_path):
    v = _verificateur(tmp_path)
    assert isinstance(v, VerificateurCitations)


def test_article_existe_version_valide(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE
    assert res.est_valide is True
    assert res.version is not None


def test_article_existe_avec_extrait_correct(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="qui cause a autrui un dommage",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE


def test_article_existe_avec_extrait_different(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="phrase completement inventee qui n'est pas dans la loi",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.TEXTE_DIFFERENT
    assert res.est_valide is False


def test_article_inexistant(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.INTROUVABLE


def test_article_avant_toutes_versions(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "1240", date(1900, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.VERSION_INCORRECTE


def test_article_apres_toutes_versions_sans_fin(tmp_path):
    """L'article 1240 est en vigueur sans date de fin."""
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "1240", date(2099, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE


def test_verifier_toutes_retourne_une_liste(tmp_path):
    v = _verificateur(tmp_path)
    citations = [
        _citation(CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1)),
        _citation(CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(2020, 1, 1)),
        _citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1)),
    ]
    resultats = v.verifier_toutes(citations)
    assert len(resultats) == 3
    assert resultats[0].statut == StatutVerification.VALIDE
    assert resultats[1].statut == StatutVerification.VALIDE
    assert resultats[2].statut == StatutVerification.INTROUVABLE


def test_melange_verdicts(tmp_path):
    """On passe un melange de citations et on verifie chaque verdict."""
    v = _verificateur(tmp_path)

    cas = [
        (_citation(CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1)),
         StatutVerification.VALIDE),
        (_citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1)),
         StatutVerification.INTROUVABLE),
        (_citation(CodeJuridique.CODE_CIVIL, "1240", date(1900, 1, 1)),
         StatutVerification.VERSION_INCORRECTE),
        (_citation(
            CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
            extrait="invente totalement",
        ), StatutVerification.TEXTE_DIFFERENT),
    ]

    for citation, attendu in cas:
        res = v.verifier(citation)
        assert res.statut == attendu, f"Attendu {attendu}, obtenu {res.statut}"


def test_extrait_normalise_accents(tmp_path):
    """Un extrait avec accents differents doit quand meme matcher."""
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="TOUT FAIT QUELCONQUE DE L'HOMME",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE
