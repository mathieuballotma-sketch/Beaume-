"""Tests du port IndexVectoriel.

1. Le faux index memoire : tous les tests unitaires.
2. L'adaptateur LanceDB : un test d'integration qui ecrit dans tmp.
"""
from pathlib import Path
import pytest

from beaume.ports.index_vectoriel import (
    ElementIndexe,
    IndexVectoriel,
    ResultatRecherche,
)
from beaume.testing.index_memoire import IndexMemoire


# --- Faux index memoire ---------------------------------------------------

def _e(id_: str, vec: list[float], **md) -> ElementIndexe:
    return ElementIndexe(id=id_, vecteur=tuple(vec), metadonnees=md or {})


def test_index_memoire_respecte_contrat():
    assert isinstance(IndexMemoire(), IndexVectoriel)


def test_index_vide_taille_zero():
    idx = IndexMemoire()
    assert idx.taille() == 0
    assert idx.rechercher([1.0, 0.0], k=3) == []


def test_ajout_et_taille():
    idx = IndexMemoire()
    idx.ajouter([_e("a", [1.0, 0.0]), _e("b", [0.0, 1.0])])
    assert idx.taille() == 2


def test_recherche_plus_proche():
    idx = IndexMemoire()
    idx.ajouter([
        _e("a", [1.0, 0.0]),
        _e("b", [0.0, 1.0]),
        _e("c", [-1.0, 0.0]),
    ])
    res = idx.rechercher([0.9, 0.1], k=1)
    assert len(res) == 1
    assert res[0].id == "a"
    assert res[0].score < 0.1


def test_recherche_k_superieur_taille():
    idx = IndexMemoire()
    idx.ajouter([_e("a", [1.0, 0.0])])
    res = idx.rechercher([1.0, 0.0], k=10)
    assert len(res) == 1


def test_recherche_k_invalide():
    idx = IndexMemoire()
    with pytest.raises(ValueError):
        idx.rechercher([1.0, 0.0], k=0)


def test_metadonnees_conservees():
    idx = IndexMemoire()
    idx.ajouter([_e("a", [1.0, 0.0], source="contrat.pdf", page=3)])
    res = idx.rechercher([1.0, 0.0], k=1)
    assert res[0].metadonnees["source"] == "contrat.pdf"
    assert res[0].metadonnees["page"] == 3


def test_vider():
    idx = IndexMemoire()
    idx.ajouter([_e("a", [1.0, 0.0])])
    idx.vider()
    assert idx.taille() == 0


def test_dimensions_differentes_rejettent():
    idx = IndexMemoire()
    idx.ajouter([_e("a", [1.0, 0.0])])
    with pytest.raises(ValueError):
        idx.rechercher([1.0, 0.0, 0.0], k=1)


# --- Integration LanceDB --------------------------------------------------

def test_lancedb_ajoute_et_recherche(tmp_path):
    from beaume.adapters.index_lancedb import IndexLanceDB
    idx = IndexLanceDB(tmp_path / "vec", "test", dimension=4)
    assert isinstance(idx, IndexVectoriel)
    idx.ajouter([
        _e("a", [1.0, 0.0, 0.0, 0.0], source="x"),
        _e("b", [0.0, 1.0, 0.0, 0.0], source="y"),
    ])
    assert idx.taille() == 2
    res = idx.rechercher([0.9, 0.1, 0.0, 0.0], k=1)
    assert res[0].id == "a"
    assert res[0].metadonnees["source"] == "x"


def test_lancedb_persiste(tmp_path):
    from beaume.adapters.index_lancedb import IndexLanceDB
    chemin = tmp_path / "vec"
    idx1 = IndexLanceDB(chemin, "test", dimension=2)
    idx1.ajouter([_e("a", [1.0, 0.0])])
    # Reouvre
    idx2 = IndexLanceDB(chemin, "test", dimension=2)
    assert idx2.taille() == 1


def test_lancedb_vider(tmp_path):
    from beaume.adapters.index_lancedb import IndexLanceDB
    idx = IndexLanceDB(tmp_path / "vec", "test", dimension=2)
    idx.ajouter([_e("a", [1.0, 0.0])])
    idx.vider()
    assert idx.taille() == 0
