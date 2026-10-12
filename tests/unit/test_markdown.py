"""Tests du rendu Markdown."""
from datetime import date
from pathlib import Path

from beaume.legal.analyse import Analyse
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Citation,
    CodeJuridique,
    ResultatVerification,
    StatutVerification,
    StatutVersion,
    VersionArticle,
)
from beaume.output.rapport import Rapport, rendre_markdown


def _version() -> VersionArticle:
    return VersionArticle(
        article_id=IdentifiantLegifrance(valeur="LEGIARTI000006904501"),
        numero="L. 1234-1",
        date_debut=date(2008, 5, 1),
        date_fin=None,
        texte="Lorsque le contrat de travail est a duree indeterminee...",
        statut=StatutVersion.EN_VIGUEUR,
        source="legifrance",
    )


def _citation_valide() -> ResultatVerification:
    c = Citation(
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L. 1234-1",
        date_reference=date(2024, 1, 1),
        extrait="contrat de travail",
    )
    return ResultatVerification(
        statut=StatutVerification.VALIDE,
        citation=c,
        version=_version(),
    )


def _citation_rejetee() -> ResultatVerification:
    c = Citation(
        code=CodeJuridique.CODE_CIVIL,
        numero="9999",
        date_reference=date(2024, 1, 1),
    )
    return ResultatVerification(
        statut=StatutVerification.INTROUVABLE,
        citation=c,
        message="Article introuvable dans le corpus.",
    )


def _rapport_avec(citations: list[ResultatVerification]) -> Rapport:
    return Rapport(
        dossier=Path("/tmp/dossier_test"),
        date_reference=date(2024, 1, 1),
        analyse=Analyse(
            contexte="Un salarie conteste son licenciement.",
            parties=["M. Dupont"],
            demandes=["Indemnisation"],
            problemes_juridiques=["Motif du licenciement"],
            citations=[v.citation for v in citations],
            date_reference=date(2024, 1, 1),
        ),
        verifications=citations,
        modele_llm="qwen2.5:7b",
        duree_s=12.34,
    )


def test_rendu_contient_titre():
    r = _rapport_avec([])
    md = rendre_markdown(r)
    assert "# Rapport d'analyse - Beaume" in md


def test_rendu_contient_metadonnees():
    r = _rapport_avec([])
    md = rendre_markdown(r)
    assert "2024-01-01" in md
    assert "qwen2.5:7b" in md
    assert "12.34 s" in md


def test_rendu_contient_contexte():
    r = _rapport_avec([])
    md = rendre_markdown(r)
    assert "Un salarie conteste son licenciement." in md


def test_rendu_contient_parties_et_demandes():
    r = _rapport_avec([])
    md = rendre_markdown(r)
    assert "## Parties" in md
    assert "M. Dupont" in md
    assert "## Demandes" in md
    assert "Indemnisation" in md


def test_rendu_avec_citation_valide():
    r = _rapport_avec([_citation_valide()])
    md = rendre_markdown(r)
    assert "Articles applicables (verifies)" in md
    assert "L. 1234-1" in md
    assert "LEGIARTI000006904501" in md
    assert "legifrance.gouv.fr" in md


def test_rendu_sans_citation_valide():
    r = _rapport_avec([])
    md = rendre_markdown(r)
    assert "(aucune citation verifiee)" in md


def test_rendu_avec_citation_rejetee():
    r = _rapport_avec([_citation_rejetee()])
    md = rendre_markdown(r)
    assert "citations rejetees" in md
    assert "9999" in md
    assert "introuvable" in md


def test_rendu_contient_note_transparence():
    r = _rapport_avec([])
    md = rendre_markdown(r)
    assert "Note de transparence" in md
    assert "verifie par un avocat" in md


def test_compteurs_citations():
    r = _rapport_avec([_citation_valide(), _citation_rejetee()])
    assert len(r.citations_valides) == 1
    assert len(r.citations_rejetees) == 1
