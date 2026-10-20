"""Tests de l'adaptateur SourceDila.

Ces tests utilisent la base DILA réelle si elle est présente, sinon ils
sont ignorés (skip). Ils vérifient les invariants suivants :

- L1233-3 a 7 versions, 1240 a 2 versions, 200 CGI a ~59 versions.
- Toutes les versions d'un même article partagent le même article_id.
- Un round-trip par DepotSQLite fonctionne.
- Les statuts vides sont mappés en INCONNU.

Tests de non-régression (audit 2026-10-20, base synthétique) :

- Collision date_debut : version ouverte préférée.
- Date de fin invalide : statut INCONNU (pas EN_VIGUEUR).
- trouver_par_numero ambigu : retourne None.
- trouver_par_numero avec article_famille_id : cible la bonne famille.
- iter_articles : ne coupe pas les versions (pas de LIMIT SQL).
"""
from __future__ import annotations

import sqlite3
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def source() -> SourceDila:
    with SourceDila(CHEMIN_DILA, filtrer_conflits=True) as s:
        yield s


@pytest.fixture(scope="module")
def articles_connus(source: SourceDila) -> dict[str, object]:
    return {
        "L1233-3": source.trouver_par_numero("L1233-3", "LEGITEXT000006072050"),
        "1240": source.trouver_par_numero("1240", "LEGITEXT000006070721"),
        "200": source.trouver_par_numero("200", "LEGITEXT000006069577"),
    }


@pytest.fixture
def source_synthetique(tmp_path):
    """Crée une mini-base DILA synthétique pour tester les cas limites.

    Contient :
    - L9999-1 : deux versions même date_debut, une fermée + une ouverte
    - L9999-2 : une version avec date_fin invalide ("inconnue")
    - L9999-3 : deux familles distinctes (FAMILLE_A, FAMILLE_B)
    - L9999-4 : sept versions (test iter_articles sans LIMIT SQL)
    """
    chemin = tmp_path / "dila_synthetique.sqlite"
    conn = sqlite3.connect(chemin)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE versions_articles_sans_conflit_source (
            article_id TEXT, code TEXT, numero TEXT,
            date_debut TEXT, date_fin TEXT, statut TEXT,
            texte TEXT, article_famille_id TEXT
        )
    """)
    cur.execute("""
        CREATE VIEW versions_articles AS
        SELECT * FROM versions_articles_sans_conflit_source
    """)

    # Cas 1 : collision date_debut (une fermée + une ouverte)
    cur.execute(
        "INSERT INTO versions_articles_sans_conflit_source VALUES "
        "('LEGIARTI_VERSION_FERMEE', 'LEGITEXT000006072050', 'L9999-1', "
        "'2015-01-01', '2020-01-01', 'ABROGE', 'Texte fermé', "
        "'LEGIARTI_FAMILLE_1')"
    )
    cur.execute(
        "INSERT INTO versions_articles_sans_conflit_source VALUES "
        "('LEGIARTI_VERSION_OUVERTE', 'LEGITEXT000006072050', 'L9999-1', "
        "'2015-01-01', '2999-01-01', 'VIGUEUR', 'Texte ouvert', "
        "'LEGIARTI_FAMILLE_1')"
    )

    # Cas 2 : date_fin invalide
    cur.execute(
        "INSERT INTO versions_articles_sans_conflit_source VALUES "
        "('LEGIARTI_DATE_INVALIDE', 'LEGITEXT000006072050', 'L9999-2', "
        "'2015-01-01', 'inconnue', 'VIGUEUR', 'Texte invalide', "
        "'LEGIARTI_FAMILLE_2')"
    )

    # Cas 3 : deux familles même numéro
    cur.execute(
        "INSERT INTO versions_articles_sans_conflit_source VALUES "
        "('LEGIARTI_FAMILLE_A_V1', 'LEGITEXT000006072050', 'L9999-3', "
        "'2015-01-01', '2999-01-01', 'VIGUEUR', 'Famille A', "
        "'LEGIARTI_FAMILLE_A')"
    )
    cur.execute(
        "INSERT INTO versions_articles_sans_conflit_source VALUES "
        "('LEGIARTI_FAMILLE_B_V1', 'LEGITEXT000006072050', 'L9999-3', "
        "'2018-01-01', '2999-01-01', 'VIGUEUR', 'Famille B', "
        "'LEGIARTI_FAMILLE_B')"
    )

    # Cas 4 : article à 7 versions
    for i in range(7):
        cur.execute(
            "INSERT INTO versions_articles_sans_conflit_source VALUES "
            "(?, 'LEGITEXT000006072050', 'L9999-4', ?, ?, 'VIGUEUR', ?, "
            "'LEGIARTI_FAMILLE_C')",
            (
                f"LEGIARTI_C_{i}",
                f"2010-01-{i+1:02d}",
                f"2020-01-{i+1:02d}",
                f"Texte {i}",
            ),
        )

    conn.commit()
    conn.close()

    with SourceDila(chemin, filtrer_conflits=True) as s:
        yield s


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
    assert _parse_date_fin("2999-01-01") == (None, True)
    assert _parse_date_fin("2222-02-22") == (None, True)
    assert _parse_date_fin("2024-06-01") == (date(2024, 6, 1), True)


def test_parse_date_fin_invalide_retourne_false():
    """Régression 2026-10-20 : date_fin invalide -> (None, False)."""
    assert _parse_date_fin("inconnue") == (None, False)
    assert _parse_date_fin("not-a-date") == (None, False)


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
# Tests sur la base DILA réelle
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
    assert len(article.versions) == 7
    assert article.code == CodeJuridique.CODE_TRAVAIL


def test_1240_a_deux_versions(articles_connus):
    article = articles_connus["1240"]
    assert article is not None, "1240 absent"
    assert len(article.versions) == 2
    assert article.code == CodeJuridique.CODE_CIVIL


def test_200_cgi_a_au_moins_55_versions(articles_connus):
    article = articles_connus["200"]
    assert article is not None, "200 CGI absent"
    assert len(article.versions) >= 55
    dates = [v.date_debut for v in article.versions]
    assert len(dates) == len(set(dates))


def test_toutes_versions_partagent_le_meme_article_id(articles_connus):
    for numero, article in articles_connus.items():
        assert article is not None, f"{numero} non trouvé"
        ids = {v.article_id.valeur for v in article.versions}
        assert len(ids) == 1, (
            f"{numero} : les versions doivent partager un seul article_id"
        )
        assert list(ids)[0] == article.id.valeur


def test_round_trip_depot_sqlite(source: SourceDila, tmp_path):
    from beaume.adapters.depot_sqlite import DepotSQLite

    article = source.trouver_par_numero("L1233-3", "LEGITEXT000006072050")
    assert article is not None

    depot = DepotSQLite(tmp_path / "test_v2.sqlite")
    depot.enregistrer([article])

    date_ref = date(2020, 1, 1)
    res = depot.trouver(CodeJuridique.CODE_TRAVAIL, "L1233-3", date_ref)
    assert res is not None
    art, ver = res
    assert art.numero == "L1233-3"
    assert ver is not None
    assert ver.date_debut <= date_ref


# ---------------------------------------------------------------------------
# Tests de non-régression (audit 2026-10-20, base synthétique)
# ---------------------------------------------------------------------------

def test_collision_date_debut_garde_version_ouverte(source_synthetique: SourceDila):
    """Régression 2026-10-20 : en cas de collision date_debut, la version
    ouverte gagne (pas la version fermée)."""
    article = source_synthetique.trouver_par_numero(
        "L9999-1", "LEGITEXT000006072050",
    )
    assert article is not None
    assert len(article.versions) == 1
    version = article.versions[0]
    assert version.date_fin is None, (
        "La version ouverte doit gagner la collision, "
        f"trouvé date_fin={version.date_fin}"
    )
    assert "LEGIARTI_VERSION_OUVERTE" in version.source, (
        f"La version conservée doit être l'ouverte, trouvé {version.source}"
    )


def test_date_fin_invalide_marque_inconnu(source_synthetique: SourceDila):
    """Régression 2026-10-20 : une date_fin invalide doit forcer INCONNU,
    pas laisser passer en EN_VIGUEUR éternel."""
    article = source_synthetique.trouver_par_numero(
        "L9999-2", "LEGITEXT000006072050",
    )
    assert article is not None
    assert len(article.versions) == 1
    version = article.versions[0]
    assert version.statut == StatutVersion.INCONNU, (
        f"date_fin invalide doit forcer INCONNU, trouvé {version.statut}"
    )
    assert version.date_fin is None


def test_trouver_par_numero_ambigu_retourne_none(source_synthetique: SourceDila):
    """Régression 2026-10-20 : si plusieurs familles partagent le même
    numéro, trouver_par_numero retourne None (ne pas deviner)."""
    article = source_synthetique.trouver_par_numero(
        "L9999-3", "LEGITEXT000006072050",
    )
    assert article is None, (
        "trouver_par_numero doit retourner None sur ambiguïté"
    )


def test_trouver_par_numero_avec_famille_id(source_synthetique: SourceDila):
    """Régression 2026-10-20 : le paramètre article_famille_id permet de
    cibler une famille précise en cas d'ambiguïté."""
    article = source_synthetique.trouver_par_numero(
        "L9999-3", "LEGITEXT000006072050",
        article_famille_id="LEGIARTI_FAMILLE_A",
    )
    assert article is not None
    assert article.id.valeur == "LEGIARTI_FAMILLE_A"
    assert article.versions[0].texte == "Famille A"


def test_iter_articles_ne_coupe_pas_les_versions(source_synthetique: SourceDila):
    """Régression 2026-10-20 : iter_articles ne met pas de LIMIT SQL,
    donc un article à 7 versions les conserve toutes."""
    articles = {a.numero: a for a in source_synthetique.iter_articles()}
    assert "L9999-4" in articles
    assert len(articles["L9999-4"].versions) == 7, (
        f"L9999-4 doit garder 7 versions, trouvé "
        f"{len(articles['L9999-4'].versions)}"
    )