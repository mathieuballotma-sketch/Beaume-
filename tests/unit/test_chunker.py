"""Tests du decoupage en chunks."""
import pytest

from beaume.application.chunker import Chunk, decouper


def test_texte_vide():
    assert decouper("") == []


def test_texte_espaces_seulement():
    assert decouper("   \n\n  \n") == []


def test_texte_court_un_seul_chunk():
    chunks = decouper("Un seul paragraphe court.")
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert "paragraphe court" in chunks[0].texte


def test_deux_paragraphes_courts_dans_un_chunk():
    texte = "Premier paragraphe.\n\nDeuxieme paragraphe."
    chunks = decouper(texte, taille_cible=200)
    assert len(chunks) == 1
    assert "Premier" in chunks[0].texte
    assert "Deuxieme" in chunks[0].texte


def test_plusieurs_paragraphes_plusieurs_chunks():
    paragraphes = [f"Paragraphe numero {i} avec du contenu." for i in range(20)]
    texte = "\n\n".join(paragraphes)
    chunks = decouper(texte, taille_cible=150, chevauchement=30)
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.index == i


def test_positions_correctes():
    texte = "Premier paragraphe ici.\n\nDeuxieme paragraphe la."
    chunks = decouper(texte, taille_cible=500)
    c = chunks[0]
    assert texte[c.debut_car:c.fin_car] == c.texte


def test_paragraphe_enorme_decoupe_brut():
    texte = "mot " * 500
    chunks = decouper(texte, taille_cible=200, chevauchement=20)
    assert len(chunks) >= 10
    for c in chunks:
        assert c.longueur <= 200


def test_chevauchement_invalide():
    with pytest.raises(ValueError):
        decouper("abc", taille_cible=100, chevauchement=100)
    with pytest.raises(ValueError):
        decouper("abc", taille_cible=100, chevauchement=-1)


def test_taille_cible_invalide():
    with pytest.raises(ValueError):
        decouper("abc", taille_cible=0)


def test_deterministe():
    texte = "Alpha.\n\nBeta.\n\nGamma.\n\nDelta."
    a = decouper(texte, taille_cible=20, chevauchement=5)
    b = decouper(texte, taille_cible=20, chevauchement=5)
    assert [c.texte for c in a] == [c.texte for c in b]
