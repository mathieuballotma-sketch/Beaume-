"""Verifie que le chunker propage fichier et pages."""
from __future__ import annotations

from beaume.application.chunker import decouper_pages
from beaume.ports.extracteur import PageExtraite


def _pages_courtes() -> list[PageExtraite]:
    textes = [
        "Page 1 : premier paragraphe.",
        "Page 2 : deuxieme paragraphe.",
        "Page 3 : troisieme paragraphe.",
    ]
    pages = []
    offset = 0
    for i, t in enumerate(textes, start=1):
        pages.append(PageExtraite(
            numero=i,
            texte=t,
            debut_car=offset,
            fin_car=offset + len(t),
        ))
        offset += len(t) + 2
    return pages


def test_chunk_unitaire_couvre_toutes_les_pages():
    chunks = decouper_pages(_pages_courtes(), "test.pdf", taille_cible=200)
    assert len(chunks) == 1
    assert chunks[0].page_debut == 1
    assert chunks[0].page_fin == 3
    assert chunks[0].fichier == "test.pdf"


def test_chunks_multiples_ont_une_page_chacun():
    chunks = decouper_pages(
        _pages_courtes(), "test.pdf",
        taille_cible=30, chevauchement=5,
    )
    assert len(chunks) >= 3
    for c in chunks:
        assert c.fichier == "test.pdf"
        assert 1 <= c.page_debut <= 3
        assert c.page_debut <= c.page_fin


def test_chunk_vide_retourne_liste_vide():
    assert decouper_pages([], "vide.pdf") == []


def test_pages_vides_retournent_liste_vide():
    pages = [PageExtraite(numero=1, texte="", debut_car=0, fin_car=0)]
    assert decouper_pages(pages, "vide.pdf") == []