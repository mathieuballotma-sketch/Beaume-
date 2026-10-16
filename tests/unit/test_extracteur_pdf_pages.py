"""Verifie que l'extracteur PDF conserve les pages et les offsets."""
from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from beaume.adapters.extracteur_pdf import ExtracteurPDF


@pytest.fixture
def pdf_3_pages(tmp_path: Path) -> Path:
    chemin = tmp_path / "test.pdf"
    doc = pymupdf.open()
    for texte in ["Page 1 contenu", "Page 2 contenu", "Page 3 contenu"]:
        page = doc.new_page()
        page.insert_text((50, 50), texte)
    doc.save(str(chemin))
    doc.close()
    return chemin


def test_extraire_avec_pages_retourne_3_pages(pdf_3_pages: Path):
    extracteur = ExtracteurPDF()
    pages = extracteur.extraire_avec_pages(pdf_3_pages)
    assert len(pages) == 3
    assert [p.numero for p in pages] == [1, 2, 3]


def test_offsets_sont_coherents(pdf_3_pages: Path):
    extracteur = ExtracteurPDF()
    pages = extracteur.extraire_avec_pages(pdf_3_pages)
    for page in pages:
        assert page.debut_car < page.fin_car
        assert len(page.texte) == page.fin_car - page.debut_car


def test_extraction_avec_pages_contient_texte(pdf_3_pages: Path):
    extracteur = ExtracteurPDF()
    pages = extracteur.extraire_avec_pages(pdf_3_pages)
    assert "Page 1" in pages[0].texte
    assert "Page 2" in pages[1].texte
    assert "Page 3" in pages[2].texte


def test_extraire_reste_compatible(pdf_3_pages: Path):
    extracteur = ExtracteurPDF()
    texte = extracteur.extraire(pdf_3_pages)
    assert isinstance(texte, str)
    assert "Page 1" in texte
    assert "Page 2" in texte
    assert "Page 3" in texte


def test_extracteur_respecte_protocole():
    from beaume.ports.extracteur import Extracteur
    assert isinstance(ExtracteurPDF(), Extracteur)