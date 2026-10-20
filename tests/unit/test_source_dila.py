"""Tests de l'adaptateur SourceDila.

Ces tests utilisent la base DILA réelle si elle est présente, sinon ils
sont ignorés (skip). Ils vérifient les invariants suivants :

- L1233-3 a 7 versions, 1240 a 2 versions.
- 200 du CGI a ~59 versions après dédoublonnage (60 brutes, 1 doublon
  DILA sur date_debut=1999-03-31).
- Toutes les versions d'un même article partagent le même article_id.
- Un round-trip par DepotSQLite fonctionne (régression du 2026-10-20).
- Les statuts vides sont mappés en INCONNU.
"""
from __future__ import annotations

from datetime import date

import pytest

from beaume.adapters.source_dila import (
    SourceDila,
    _map_statut,
    _parse_date_debut,
    _parse_date_fin,
)
from beaume.config import paths
from beaume.legal.model import CodeJuridique, StatutVersion


CHEMIN_DILA = paths.VECTOR / "legi_dila_v2" / "legi_dila.sqlite"

pytestmark = pytest.mark.skipif(
    not CHEMIN_DILA.is_file(),
    reason=f"Base DILA absente : {CHEMIN_DILA}",
)


@pytest.fixture(scope="module")
def source() -> SourceDila:
    with SourceDila(CHEMIN_DILA, filtrer_conflits=True) as s:
        yield s


@pytest.fixture(scope="module")
def articles_connus(source: SourceDila) -> dict[str, object]:
    """Charge une seule fois les 3 articles de référence."""
    return {
        "L1233-3": source.trouver_par_numero("L1233-3", "LEGITEXT000006072050"),
        "1240": source.trouver_par_numero("1240", "LEGITEXT000006070721"),
        "200": source.trouver_par_numero("200", "LEGITEXT000006069577"),
    }


# ---------------------------------------------------------------------------
# Tests unitaires (sans DB)
# ---------------------------------------------------------------------------

def test_parse_date_debut_sentinelle():
    assert _parse_date_debut("2999-01-01") == date(2999, 1, 1)
    assert _parse_date_debut("2222-02-22") == date(2222, 2, 22)


def test_parse_date_debut_vide_ou_invalide():
    assert _parse_date_debut(None) is None
    assert _parse_date_debut("") is None
    assert _parse_date_debut("pas-une-date") is None


def test_parse_date_fin_sentinelle_devient_none():
    assert _parse_date_fin("2999-01-01") is None
    assert _parse_date_fin("2222-02-22") is None
    assert _parse_date_fin("2024-06-01") == date(2024, 6, 1)


def test_map_statut_vide_inconnu():
    assert _map_statut("", date(2024, 1, 1)) == StatutVersion.INCONNU
    assert _map_statut("MANQUANT", date(2024, 1, 1)) == StatutVersion.INCONNU


def test_map_statut_vigueur():
    assert _map_statut("VIGUEUR", date(2024, 1, 1)) == StatutVersion.EN_VIGUEUR
    assert _map_statut("MODIFIE", date(2024, 1, 1)) == StatutVersion.MODIFIE
    assert _map_statut("ABROGE", date(2024, 1, 1)) == StatutVersion.ABROGE


def test_map_statut_differe():
    assert _map_statut("VIGUEUR_DIFF", date(2099, 1, 1)) == StatutVersion.FUTUR
    assert _map_statut("VIGUEUR_DIFF", date(2020, 1, 1)) == StatutVersion.EN_VIGUEUR


def test_map_statut_abroge_diff_inconnu():
    assert _map_statut("ABROGE_DIFF", date(2020, 1, 1)) == StatutVersion.INCONNU
    assert _map_statut("ABROGE_DIFF", date(2099, 1, 1)) == StatutVersion.INCONNU


# ---------------------------------------------------------------------------
# Tests sur la base DILA
# ---------------------------------------------------------------------------

def test_compter_code_travail(source: SourceDila):
    n = source.compter(codes=("LEGITEXT000006072050",))
    assert n > 40000, f"Attendu > 40000, trouvé {n}"


def test_compter_code_civil(source: SourceDila):
    n = source.compter(codes=("LEGITEXT000006070721",))
    assert n > 6000, f"Attendu > 6000, trouvé {n}"


def test_l1233_3_a_sept_versions(articles_connus):
    article = articles_connus["L1233-3"]
    assert article is not None, "L1233-3 absent"
    assert len(article.versions) == 7, (
        f"L1233-3 doit avoir 7 versions, trouvé {len(article.versions)}"
    )
    assert article.code == CodeJuridique.CODE_TRAVAIL


def test_1240_a_deux_versions(articles_connus):
    article = articles_connus["1240"]
    assert article is not None, "1240 absent"
    assert len(article.versions) == 2, (
        f"1240 doit avoir 2 versions, trouvé {len(article.versions)}"
    )
    assert article.code == CodeJuridique.CODE_CIVIL


def test_200_cgi_a_au_moins_55_versions(articles_connus):
    """L'article 200 du CGI a 60 versions brutes dans DILA.

    Le dédoublonnage par date_debut (PRIMARY KEY de `versions`) retire
    les doublons DILA. Sur cet article, 1 version a été retirée
    (date_debut=1999-03-31, LEGIARTI000006314630 vs 000006314631).
    On vérifie qu'il reste au moins 55 versions, et qu'il n'y a pas de
    doublon de date_debut.
    """
    article = articles_connus["200"]
    assert article is not None, "200 CGI absent"
    assert len(article.versions) >= 55, (
        f"200 CGI doit avoir au moins 55 versions après dédoublonnage, "
        f"trouvé {len(article.versions)}"
    )
    dates = [v.date_debut for v in article.versions]
    assert len(dates) == len(set(dates)), (
        "Deux versions partagent la même date_debut"
    )


def test_toutes_versions_partagent_le_meme_article_id(articles_connus):
    """Régression du 2026-10-20 : toutes les versions d'un même article
    doivent partager le même VersionArticle.article_id (famille_id),
    sinon DepotSQLite.trouver() ne joint jamais articles et versions.
    """
    for numero, article in articles_connus.items():
        assert article is not None, f"{numero} non trouvé"
        ids = {v.article_id.valeur for v in article.versions}
        assert len(ids) == 1, (
            f"{numero} : les versions doivent partager un seul article_id, "
            f"trouvé {ids}"
        )
        assert list(ids)[0] == article.id.valeur, (
            f"{numero} : VersionArticle.article_id doit être égal à Article.id"
        )


def test_round_trip_depot_sqlite(source: SourceDila, tmp_path):
    """Régression du 2026-10-20 : DepotSQLite.enregistrer puis trouver
    doivent fonctionner sur les données DILA. Avant le fix, la jointure
    articles/versions ne trouvait rien (0 multi-versions en base).
    """
    from beaume.adapters.depot_sqlite import DepotSQLite

    article = source.trouver_par_numero("L1233-3", "LEGITEXT000006072050")
    assert article is not None

    depot = DepotSQLite(tmp_path / "test_v2.sqlite")
    depot.enregistrer([article])

    date_ref = date(2020, 1, 1)
    res = depot.trouver(CodeJuridique.CODE_TRAVAIL, "L1233-3", date_ref)
    assert res is not None, (
        "trouver() doit retourner un article après enregistrement"
    )
    art, ver = res
    assert art.numero == "L1233-3"
    assert ver is not None
    assert ver.date_debut <= date_ref