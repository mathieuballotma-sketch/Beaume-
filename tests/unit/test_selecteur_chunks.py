"""Tests du selecteur de chunks."""
import pytest

from beaume.application.chunker import Chunk
from beaume.application.selecteur_chunks import (
    SIGNATURES,
    ChunkSelectionne,
    SelectionChunks,
    SelecteurChunks,
    _normaliser,
    _score_question,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(index: int, texte: str) -> Chunk:
    return Chunk(
        index=index,
        texte=texte,
        debut_car=0,
        fin_car=len(texte),
    )


# ---------------------------------------------------------------------------
# Tests : normalisation
# ---------------------------------------------------------------------------

def test_normaliser_minuscules():
    assert _normaliser("BONJOUR") == "bonjour"


def test_normaliser_sans_accents():
    assert _normaliser("harcèlement") == "harcelement"


def test_normaliser_sans_ponctuation():
    assert _normaliser("M. Dupont, le 15/09.") == "m dupont le 15 09"


def test_normaliser_vide():
    assert _normaliser("") == ""
    assert _normaliser("   ") == ""


# ---------------------------------------------------------------------------
# Tests : score
# ---------------------------------------------------------------------------

def test_score_vide():
    assert _score_question("", SIGNATURES["faits"]) == 0.0


def test_score_positif_sur_mot_cle():
    score = _score_question("il a survenu un accident", SIGNATURES["faits"])
    assert score > 0


def test_score_zero_sur_texte_neutre():
    score = _score_question("pomme banane orange", SIGNATURES["faits"])
    assert score == 0.0


def test_score_normalise_par_longueur():
    """Un chunk court avec un mot-cle score plus fort qu'un long."""
    court = _score_question("survenu", SIGNATURES["faits"])
    long = _score_question(
        "survenu " + " ".join(["mot" for _ in range(100)]),
        SIGNATURES["faits"],
    )
    assert court > long


# ---------------------------------------------------------------------------
# Tests : selecteur
# ---------------------------------------------------------------------------

def test_selecteur_chunks_vide():
    s = SelecteurChunks()
    res = s.selectionner([])
    assert res.chunks_totaux == 0
    assert res.chunks_utilises == 0
    for question in SIGNATURES:
        assert res.par_question[question] == []


def test_selecteur_trouve_chunk_faits():
    chunks = [
        _chunk(0, "Le 15 septembre, une convocation est survenue."),
        _chunk(1, "Un chien aboie dans le jardin."),
        _chunk(2, "Pomme banane cerise."),
    ]
    s = SelecteurChunks(top_par_question=1)
    res = s.selectionner(chunks)
    top_faits = res.par_question["faits"]
    assert len(top_faits) == 1
    assert top_faits[0].chunk.index == 0


def test_selecteur_trouve_chunk_parties():
    chunks = [
        _chunk(0, "Monsieur Jean Dupont, demeurant a Lyon."),
        _chunk(1, "Le chat dort."),
    ]
    s = SelecteurChunks(top_par_question=1)
    res = s.selectionner(chunks)
    top = res.par_question["parties"]
    assert len(top) == 1
    assert top[0].chunk.index == 0


def test_selecteur_trouve_chunk_demandes():
    chunks = [
        _chunk(0, "Je sollicite votre assistance pour contester."),
        _chunk(1, "Rien de special ici."),
    ]
    s = SelecteurChunks(top_par_question=1)
    res = s.selectionner(chunks)
    top = res.par_question["demandes"]
    assert len(top) == 1
    assert top[0].chunk.index == 0


def test_selecteur_trouve_chunk_juridique():
    chunks = [
        _chunk(0, "Ce licenciement constitue un harcelement moral."),
        _chunk(1, "Un jour il a plu."),
    ]
    s = SelecteurChunks(top_par_question=1)
    res = s.selectionner(chunks)
    top = res.par_question["problemes_juridiques"]
    assert len(top) == 1
    assert top[0].chunk.index == 0


def test_selecteur_respecte_top():
    chunks = [
        _chunk(i, f"Le fait numero {i} est survenu.")
        for i in range(10)
    ]
    s = SelecteurChunks(top_par_question=3)
    res = s.selectionner(chunks)
    assert len(res.par_question["faits"]) <= 3


def test_selecteur_evite_doublons_entre_questions():
    """Les chunks selectionnes restent individualises par question."""
    chunks = [_chunk(0, "Le licenciement est survenu et je sollicite.")]
    s = SelecteurChunks(top_par_question=3)
    res = s.selectionner(chunks)
    # Le meme chunk peut apparaitre dans plusieurs questions (c'est OK)
    assert res.chunks_utilises == 1  # en terme de chunks uniques


def test_selecteur_top_invalide():
    with pytest.raises(ValueError):
        SelecteurChunks(top_par_question=0)


def test_selecteur_score_min_invalide():
    with pytest.raises(ValueError):
        SelecteurChunks(score_min=-1)


def test_formater_pour_prompt():
    chunks = [
        _chunk(0, "Le 15 septembre, une convocation est survenue."),
        _chunk(1, "Monsieur Jean Dupont, demeurant a Lyon."),
    ]
    s = SelecteurChunks(top_par_question=1)
    res = s.selectionner(chunks)
    texte = s.formater_pour_prompt(res)
    assert "=== FAITS ===" in texte
    assert "=== PARTIES ===" in texte
    assert "convocation" in texte


def test_formater_selection_vide():
    s = SelecteurChunks()
    res = s.selectionner([])
    texte = s.formater_pour_prompt(res)
    assert texte == ""


def test_selection_deterministe():
    """Meme entree = meme sortie."""
    chunks = [
        _chunk(0, "Le fait est survenu."),
        _chunk(1, "Monsieur Dupont."),
        _chunk(2, "Je demande reparation."),
    ]
    s = SelecteurChunks()
    r1 = s.selectionner(chunks)
    r2 = s.selectionner(chunks)
    for q in SIGNATURES:
        assert [c.chunk.index for c in r1.par_question[q]] == \
               [c.chunk.index for c in r2.par_question[q]]
