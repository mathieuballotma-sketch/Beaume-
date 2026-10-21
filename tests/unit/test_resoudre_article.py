"""Tests de DepotSQLite.resoudre_article (voie stricte).

Chaque test couvre une ligne de la table de decision du port
beaume/ports/resolveur_articles.py. Les tests ne touchent pas a la
base 275 Mo : ils utilisent tous tmp_path et une base SQLite neuve.
"""
from datetime import date

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)
from beaume.ports.resolveur_articles import StatutResolution


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _version(
    article_id: str,
    numero: str,
    debut: date,
    fin: date | None,
    *,
    statut: StatutVersion = StatutVersion.EN_VIGUEUR,
    source: str | None = None,
    texte: str = "texte",
) -> VersionArticle:
    return VersionArticle(
        article_id=IdentifiantLegifrance(valeur=article_id),
        numero=numero,
        date_debut=debut,
        date_fin=fin,
        texte=texte,
        statut=statut,
        source=source or f"DILA-LEGI:{article_id}",
    )


def _article(
    famille: str,
    code: CodeJuridique,
    numero: str,
    versions: list[VersionArticle],
) -> Article:
    return Article(
        id=IdentifiantLegifrance(valeur=famille),
        code=code,
        numero=numero,
        versions=versions,
    )


def _depot(tmp_path) -> DepotSQLite:
    return DepotSQLite(tmp_path / "legi.sqlite")


FAM = "LEGIARTI000000000001"
LEGI_V1 = "LEGIARTI000000000011"
LEGI_V2 = "LEGIARTI000000000012"


# ---------------------------------------------------------------------------
# Statut UNIQUE et appariement famille / version / LEGIARTI
# ---------------------------------------------------------------------------

def test_unique_nominal(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2016, 8, 10), None, source=f"DILA-LEGI:{LEGI_V1}"),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2020, 1, 1))
    assert r.statut == StatutResolution.UNIQUE
    assert r.article_id_famille == FAM
    assert r.version_legiarti == LEGI_V1
    assert r.version_date_debut == date(2016, 8, 10)
    assert r.code == CodeJuridique.CODE_TRAVAIL
    assert r.numero_normalise == "L1233-3"
    assert r.candidats == ()


# ---------------------------------------------------------------------------
# REFERENCE_ABSENTE
# ---------------------------------------------------------------------------

def test_reference_absente_numero_inconnu(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2016, 8, 10), None),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L9999-9", date(2020, 1, 1))
    assert r.statut == StatutResolution.REFERENCE_ABSENTE


def test_reference_absente_mauvais_code(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2016, 8, 10), None),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_CIVIL, "L1233-3", date(2020, 1, 1))
    assert r.statut == StatutResolution.REFERENCE_ABSENTE


# ---------------------------------------------------------------------------
# AUCUNE_VERSION_A_LA_DATE
# ---------------------------------------------------------------------------

def test_aucune_version_avant_premiere(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2016, 8, 10), None),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2010, 1, 1))
    assert r.statut == StatutResolution.AUCUNE_VERSION_A_LA_DATE


def test_aucune_version_apres_derniere(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2010, 1, 1), date(2015, 12, 31)),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2020, 1, 1))
    assert r.statut == StatutResolution.AUCUNE_VERSION_A_LA_DATE


# ---------------------------------------------------------------------------
# Bornes inclusives
# ---------------------------------------------------------------------------

def test_borne_debut_inclusive(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2016, 8, 10), None, source=f"DILA-LEGI:{LEGI_V1}"),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2016, 8, 10))
    assert r.statut == StatutResolution.UNIQUE


def test_borne_fin_inclusive(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2010, 1, 1), date(2015, 12, 31), source=f"DILA-LEGI:{LEGI_V1}"),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2015, 12, 31))
    assert r.statut == StatutResolution.UNIQUE


# ---------------------------------------------------------------------------
# Sentinelles de date_fin
# ---------------------------------------------------------------------------

def test_sentinelle_2999_traitee_comme_infinie(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2010, 1, 1), date(2999, 1, 1), source=f"DILA-LEGI:{LEGI_V1}"),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2999, 6, 1))
    assert r.statut == StatutResolution.UNIQUE


def test_sentinelle_2222_traitee_comme_infinie(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2010, 1, 1), date(2222, 2, 22), source=f"DILA-LEGI:{LEGI_V1}"),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2222, 6, 1))
    assert r.statut == StatutResolution.UNIQUE


# ---------------------------------------------------------------------------
# AMBIGUITE_FAMILLES
# ---------------------------------------------------------------------------

def _deux_familles(dep: DepotSQLite) -> None:
    dep.enregistrer([
        _article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
            _version(FAM, "L1233-3", date(2010, 1, 1), None, source=f"DILA-LEGI:{LEGI_V1}"),
        ]),
        _article(
            "LEGIARTI000000000002",
            CodeJuridique.CODE_TRAVAIL,
            "L1233-3",
            [_version(
                "LEGIARTI000000000002",
                "L1233-3",
                date(2015, 1, 1),
                None,
                source=f"DILA-LEGI:{LEGI_V2}",
            )],
        ),
    ])


def test_ambiguite_familles_strict_true_candidats_vides(tmp_path):
    dep = _depot(tmp_path)
    _deux_familles(dep)
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2020, 1, 1))
    assert r.statut == StatutResolution.AMBIGUITE_FAMILLES
    assert r.candidats == ()


def test_ambiguite_familles_strict_false_liste_candidats(tmp_path):
    dep = _depot(tmp_path)
    _deux_familles(dep)
    r = dep.resoudre_article(
        CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2020, 1, 1), strict=False,
    )
    assert r.statut == StatutResolution.AMBIGUITE_FAMILLES
    assert r.candidats == (FAM, "LEGIARTI000000000002")


# ---------------------------------------------------------------------------
# AMBIGUITE_VERSIONS
# ---------------------------------------------------------------------------

def _deux_versions_chevauchees(dep: DepotSQLite) -> None:
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2010, 1, 1), date(2020, 12, 31), source=f"DILA-LEGI:{LEGI_V1}"),
        _version(FAM, "L1233-3", date(2018, 1, 1), date(2025, 12, 31), source=f"DILA-LEGI:{LEGI_V2}"),
    ])])


def test_ambiguite_versions_strict_true_candidats_vides(tmp_path):
    dep = _depot(tmp_path)
    _deux_versions_chevauchees(dep)
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2019, 1, 1))
    assert r.statut == StatutResolution.AMBIGUITE_VERSIONS
    assert r.article_id_famille == FAM
    assert r.candidats == ()


def test_ambiguite_versions_strict_false_liste_candidats(tmp_path):
    dep = _depot(tmp_path)
    _deux_versions_chevauchees(dep)
    r = dep.resoudre_article(
        CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2019, 1, 1), strict=False,
    )
    assert r.statut == StatutResolution.AMBIGUITE_VERSIONS
    assert len(r.candidats) == 2
    assert any(LEGI_V1 in c for c in r.candidats)
    assert any(LEGI_V2 in c for c in r.candidats)


# ---------------------------------------------------------------------------
# Statuts de version
# ---------------------------------------------------------------------------

def test_abroge_applicable_reste_unique(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(
            FAM, "L1233-3", date(2010, 1, 1), date(2015, 12, 31),
            statut=StatutVersion.ABROGE, source=f"DILA-LEGI:{LEGI_V1}",
        ),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2012, 1, 1))
    assert r.statut == StatutResolution.UNIQUE
    assert r.version_legiarti == LEGI_V1


def test_statut_inconnu_provenance_insuffisante(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(
            FAM, "L1233-3", date(2010, 1, 1), None,
            statut=StatutVersion.INCONNU, source=f"DILA-LEGI:{LEGI_V1}",
        ),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2012, 1, 1))
    assert r.statut == StatutResolution.PROVENANCE_INSUFFISANTE
    assert r.article_id_famille == FAM
    assert r.version_date_debut == date(2010, 1, 1)
    assert r.version_legiarti is None


def test_statut_futur_provenance_insuffisante(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(
            FAM, "L1233-3", date(2010, 1, 1), None,
            statut=StatutVersion.FUTUR, source=f"DILA-LEGI:{LEGI_V1}",
        ),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2012, 1, 1))
    assert r.statut == StatutResolution.PROVENANCE_INSUFFISANTE


# ---------------------------------------------------------------------------
# Provenance insuffisante (source)
# ---------------------------------------------------------------------------

def test_source_sans_legiarti(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        VersionArticle(
            article_id=IdentifiantLegifrance(valeur=FAM),
            numero="L1233-3",
            date_debut=date(2010, 1, 1),
            date_fin=None,
            texte="x",
            statut=StatutVersion.EN_VIGUEUR,
            source="DILA-LEGI:indetermine",
        ),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2012, 1, 1))
    assert r.statut == StatutResolution.PROVENANCE_INSUFFISANTE
    assert r.version_legiarti is None


# ---------------------------------------------------------------------------
# Normalisation et entree invalide
# ---------------------------------------------------------------------------

def test_numero_humain_equivalent_a_compact(tmp_path):
    dep = _depot(tmp_path)
    dep.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [
        _version(FAM, "L1233-3", date(2010, 1, 1), None, source=f"DILA-LEGI:{LEGI_V1}"),
    ])])
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L. 1233-3", date(2012, 1, 1))
    assert r.statut == StatutResolution.UNIQUE
    assert r.numero_normalise == "L1233-3"


def test_numero_vide_donnees_incoherentes(tmp_path):
    dep = _depot(tmp_path)
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "", date(2012, 1, 1))
    assert r.statut == StatutResolution.DONNEES_INCOHERENTES


def test_code_invalide_donnees_incoherentes(tmp_path):
    """Un code qui n'existe pas dans l'enum CodeJuridique est rejete.

    Note (2026-10-21) : depuis l'acceptation des chaines dans
    resoudre_article (compatibilite avec resoudre_reference), une
    chaine "code_travail" n'est PLUS invalide — c'est un code enum
    valide. Ce test couvre donc un code reellement inconnu.
    """
    dep = _depot(tmp_path)
    r = dep.resoudre_article("code_bidon", "L1233-3", date(2012, 1, 1))
    assert r.statut == StatutResolution.DONNEES_INCOHERENTES


# ---------------------------------------------------------------------------
# ERREUR_TECHNIQUE
# ---------------------------------------------------------------------------

def test_erreur_technique_sqlite(tmp_path):
    dep = _depot(tmp_path)
    dep._conn.close()
    r = dep.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2012, 1, 1))
    assert r.statut == StatutResolution.ERREUR_TECHNIQUE
    assert r.message.startswith("sqlite:")


# ---------------------------------------------------------------------------
# Invariance a l'ordre d'insertion
# ---------------------------------------------------------------------------

def test_invariance_ordre_insertion_versions(tmp_path):
    v1 = _version(FAM, "L1233-3", date(2010, 1, 1), date(2015, 12, 31), source=f"DILA-LEGI:{LEGI_V1}")
    v2 = _version(FAM, "L1233-3", date(2016, 1, 1), None, source=f"DILA-LEGI:{LEGI_V2}")

    d1 = _depot(tmp_path / "a")
    (tmp_path / "a").mkdir(exist_ok=True)
    d1.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [v1, v2])])

    d2 = _depot(tmp_path / "b")
    (tmp_path / "b").mkdir(exist_ok=True)
    d2.enregistrer([_article(FAM, CodeJuridique.CODE_TRAVAIL, "L1233-3", [v2, v1])])

    r1 = d1.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2020, 1, 1))
    r2 = d2.resoudre_article(CodeJuridique.CODE_TRAVAIL, "L1233-3", date(2020, 1, 1))

    assert r1.statut == r2.statut == StatutResolution.UNIQUE
    assert r1.version_legiarti == r2.version_legiarti == LEGI_V2
