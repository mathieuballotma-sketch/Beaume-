"""Tests du port ChercheurArticles et de l'adaptateur FTS5."""
from pathlib import Path

import pytest

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.ports.chercheur_articles import ChercheurArticles
from beaume.utils.texte import extraire_mots_cles


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"


# ---------------------------------------------------------------------------
# Tests : extraction de mots-cles
# ---------------------------------------------------------------------------

def test_extraire_mots_cles_retire_stopwords():
    mots = extraire_mots_cles("le contrat de travail est signe par les parties")
    assert "contrat" in mots
    assert "travail" in mots
    assert "le" not in mots
    assert "de" not in mots


def test_extraire_mots_cles_retire_ponctuation():
    mots = extraire_mots_cles("Bonjour, comment ça va ?")
    assert "bonjour" in mots
    assert "comment" not in mots  # stopword
    assert "bonjour," not in mots  # ponctuation retiree


def test_extraire_mots_cles_deduplique():
    mots = extraire_mots_cles("contrat contrat contrat travail travail")
    assert mots.count("contrat") == 1
    assert mots.count("travail") == 1


def test_extraire_mots_cles_limite():
    texte = " ".join(f"motunique{i}" for i in range(50))
    mots = extraire_mots_cles(texte, limite=5)
    assert len(mots) == 5


def test_extraire_mots_cles_vide():
    assert extraire_mots_cles("") == []
    assert extraire_mots_cles("   ") == []


def test_extraire_mots_cles_limite_invalide():
    with pytest.raises(ValueError):
        extraire_mots_cles("test", limite=0)


def test_extraire_mots_cles_longueur_min():
    mots = extraire_mots_cles("a ab abc abcd")
    assert "a" not in mots
    assert "ab" not in mots
    assert "abc" in mots
    assert "abcd" in mots


# ---------------------------------------------------------------------------
# Tests : chercheur FTS5
# ---------------------------------------------------------------------------

def _depot_avec_fixture(tmp_path) -> DepotSQLite:
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    depot.enregistrer(SourceFichierLocal(FIXTURE).charger())
    return depot


def test_chercheur_respecte_contrat(tmp_path):
    depot = _depot_avec_fixture(tmp_path)
    assert isinstance(ChercheurArticlesFTS5(depot), ChercheurArticles)


def test_cherche_texte_contrat_travail(tmp_path):
    depot = _depot_avec_fixture(tmp_path)
    chercheur = ChercheurArticlesFTS5(depot)
    res = chercheur.chercher(
        "Le contrat de travail a duree indeterminee peut cesser.",
        limite=5,
    )
    assert len(res) >= 1
    assert any(r.numero == "L. 1234-1" for r in res)


def test_cherche_texte_dommage(tmp_path):
    depot = _depot_avec_fixture(tmp_path)
    chercheur = ChercheurArticlesFTS5(depot)
    res = chercheur.chercher(
        "Cette personne a cause un dommage important a autrui.",
        limite=5,
    )
    assert len(res) >= 1
    assert any(r.numero == "1240" for r in res)


def test_cherche_texte_sans_rapport(tmp_path):
    depot = _depot_avec_fixture(tmp_path)
    chercheur = ChercheurArticlesFTS5(depot)
    res = chercheur.chercher(
        "astronomie telescope mars galaxie",
        limite=5,
    )
    assert res == []


def test_cherche_texte_vide(tmp_path):
    depot = _depot_avec_fixture(tmp_path)
    chercheur = ChercheurArticlesFTS5(depot)
    assert chercheur.chercher("") == []
    assert chercheur.chercher("   ") == []


def test_cherche_limite_invalide(tmp_path):
    depot = _depot_avec_fixture(tmp_path)
    chercheur = ChercheurArticlesFTS5(depot)
    with pytest.raises(ValueError):
        chercheur.chercher("contrat", limite=0)


def test_cherche_respecte_limite(tmp_path):
    depot = _depot_avec_fixture(tmp_path)
    chercheur = ChercheurArticlesFTS5(depot)
    res = chercheur.chercher(
        "contrat travail dommage reparer",
        limite=1,
    )
    assert len(res) == 1
