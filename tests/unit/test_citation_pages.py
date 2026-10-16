"""Verifie que les pages et fichiers sont lus et affiches."""
from __future__ import annotations

from datetime import date

from beaume.application.analyse_dossier import _parse_analyse
from beaume.application.prompts import construire_prompt
from beaume.legal.model import Citation, CodeJuridique


def test_parse_analyse_lit_pages_et_fichier():
    brut = {
        "contexte": "test",
        "citations": [{
            "code": "code_civil",
            "numero": "1240",
            "extrait": "test",
            "pages": [3, 4],
            "fichier": "conclusions.pdf",
        }],
    }
    analyse = _parse_analyse(brut, date(2024, 1, 1))
    assert len(analyse.citations) == 1
    c = analyse.citations[0]
    assert c.pages == (3, 4)
    assert c.fichier == "conclusions.pdf"


def test_parse_analyse_sans_pages():
    brut = {
        "contexte": "test",
        "citations": [{
            "code": "code_civil",
            "numero": "1240",
            "extrait": "test",
        }],
    }
    analyse = _parse_analyse(brut, date(2024, 1, 1))
    c = analyse.citations[0]
    assert c.pages == ()
    assert c.fichier == ""


def test_prompt_demande_pages_et_fichier():
    prompt = construire_prompt("dossier test", [], date(2024, 1, 1))
    assert "pages" in prompt
    assert "fichier" in prompt
    assert "conclusions.pdf" in prompt


def test_citation_accepte_pages_defaut():
    c = Citation(
        code=CodeJuridique.CODE_CIVIL,
        numero="1240",
        date_reference=date(2024, 1, 1),
    )
    assert c.pages == ()
    assert c.fichier == ""