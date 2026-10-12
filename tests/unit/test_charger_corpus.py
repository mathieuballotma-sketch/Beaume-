"""Tests d'integration : chargement d'un corpus dans SQLite."""
from datetime import date
from pathlib import Path
import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.legal.model import CodeJuridique


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"
CORPUS_REEL = (
    Path(__file__).parent.parent.parent
    / "data" / "legal" / "corpus_initial.json"
)


# ---------------------------------------------------------------------------
# Tests avec la fixture (toujours presente)
# ---------------------------------------------------------------------------

def test_chargement_fixture_dans_sqlite(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    source = SourceFichierLocal(FIXTURE)
    depot.enregistrer(source.charger())
    assert depot.compter() == 2


def test_recherche_par_numero_et_date(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    source = SourceFichierLocal(FIXTURE)
    depot.enregistrer(source.charger())

    res = depot.trouver(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
    )
    assert res is not None
    _, version = res
    assert "dommage" in version.texte


def test_recherche_plein_texte_fixture(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    source = SourceFichierLocal(FIXTURE)
    depot.enregistrer(source.charger())

    res = depot.rechercher_texte("dommage", limite=5)
    assert len(res) == 1
    assert res[0].numero == "1240"


# ---------------------------------------------------------------------------
# Tests avec le corpus reel (skippable si absent)
# ---------------------------------------------------------------------------

pytestmark_reel = pytest.mark.skipif(
    not CORPUS_REEL.exists(),
    reason="data/legal/corpus_initial.json absent (non versionne)",
)


@pytestmark_reel
def test_corpus_reel_charge_5_articles(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    source = SourceFichierLocal(CORPUS_REEL)
    articles = source.charger()
    assert len(articles) == 5


@pytestmark_reel
def test_corpus_reel_contient_les_bons_codes(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    source = SourceFichierLocal(CORPUS_REEL)
    depot.enregistrer(source.charger())

    codes = {
        row for row in _lister_codes(depot)
    }
    assert ("code_civil", "1240") in codes
    assert ("code_travail", "L. 1234-1") in codes
    assert ("code_travail", "L. 1152-1") in codes


@pytestmark_reel
def test_corpus_reel_trouve_article_travail(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    source = SourceFichierLocal(CORPUS_REEL)
    depot.enregistrer(source.charger())

    res = depot.trouver(
        CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(2024, 1, 1),
    )
    assert res is not None
    _, version = res
    assert "contrat de travail" in version.texte


@pytestmark_reel
def test_corpus_reel_recherche_harcelement(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    source = SourceFichierLocal(CORPUS_REEL)
    depot.enregistrer(source.charger())

    res = depot.rechercher_texte("harcelement", limite=5)
    assert len(res) >= 1
    assert any(r.numero == "L. 1152-1" for r in res)


@pytestmark_reel
def test_corpus_reel_recherche_conge_paye(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    source = SourceFichierLocal(CORPUS_REEL)
    depot.enregistrer(source.charger())

    res = depot.rechercher_texte("conge", limite=5)
    assert len(res) >= 1
    assert any(r.numero == "L. 3141-3" for r in res)


def _lister_codes(depot):
    """Petit helper : lit les codes+numero depuis le depot."""
    import sqlite3
    c = sqlite3.connect(str(depot.chemin))
    try:
        for row in c.execute(
            "SELECT code, numero FROM articles ORDER BY code, numero"
        ):
            yield (row[0], row[1])
    finally:
        c.close()
