"""Tests du verificateur de citations."""
from datetime import date
from pathlib import Path

import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article,
    Citation,
    CodeJuridique,
    StatutVersion,
    StatutVerification,
    VersionArticle,
)
from beaume.ports.verificateur_citations import VerificateurCitations


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"

EXTRAIT_1240 = "qui cause a autrui un dommage"
EXTRAIT_L1234_1 = "peut toujours cesser par la volonte d'une des parties contractantes"


def _verificateur(tmp_path) -> VerificateurStandard:
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    depot.enregistrer(SourceFichierLocal(FIXTURE).charger())
    return VerificateurStandard(depot)


def _citation(code, numero, d, extrait=None) -> Citation:
    return Citation(
        code=code,
        numero=numero,
        date_reference=d,
        extrait=extrait,
    )


def test_verificateur_respecte_contrat(tmp_path):
    v = _verificateur(tmp_path)
    assert isinstance(v, VerificateurCitations)


def test_article_existe_version_valide(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait=EXTRAIT_1240,
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE
    assert res.est_valide is True
    assert res.version is not None


def test_article_sans_extrait_est_rejete(tmp_path):
    """Une citation sans extrait n'est pas verifiable : EXTRAIT_MANQUANT."""
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.EXTRAIT_MANQUANT
    assert res.est_valide is False


def test_article_avec_extrait_vide_est_rejete(tmp_path):
    """Un extrait vide (espaces) compte comme absent."""
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="   ",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.EXTRAIT_MANQUANT


def test_article_existe_avec_extrait_correct(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="qui cause a autrui un dommage",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE


def test_article_existe_avec_extrait_different(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="phrase completement inventee qui n'est pas dans la loi",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.TEXTE_DIFFERENT
    assert res.est_valide is False


def test_article_inexistant(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.INTROUVABLE


def test_numero_article_absent_est_distingue_dun_article_introuvable(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_TRAVAIL, "", date(2025, 1, 1))

    res = v.verifier(c)

    assert res.statut == StatutVerification.NUMERO_MANQUANT
    assert res.est_valide is False


def test_article_avant_toutes_versions(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "1240", date(1900, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.VERSION_INCORRECTE


def test_article_a_versions_bornees_est_connu_hors_de_sa_periode(tmp_path):
    """Une version uniquement entre 2000 et 2010 ne doit pas devenir
    INTROUVABLE lorsqu'on vérifie une date en 2020."""
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    identifiant = IdentifiantLegifrance(valeur="LEGIARTI000099999999")
    depot.enregistrer([
        Article(
            id=identifiant,
            code=CodeJuridique.CODE_TRAVAIL,
            numero="L. 9999-9",
            versions=[
                VersionArticle(
                    article_id=identifiant,
                    numero="L. 9999-9",
                    date_debut=date(2000, 1, 1),
                    date_fin=date(2010, 12, 31),
                    texte="Version historique de test.",
                    statut=StatutVersion.ABROGE,
                    source="fixture-test",
                )
            ],
        )
    ])
    verificateur = VerificateurStandard(depot)

    resultat = verificateur.verifier(
        _citation(
            CodeJuridique.CODE_TRAVAIL,
            "L. 9999-9",
            date(2020, 1, 1),
            extrait="extrait quelconque",
        )
    )

    assert resultat.statut == StatutVerification.VERSION_INCORRECTE


def test_version_marquee_abrogee_peut_etre_valide_a_une_date_historique(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    identifiant = IdentifiantLegifrance(valeur="LEGIARTI000099999998")
    texte = "Texte historique applicable pendant la periode de test."
    depot.enregistrer([
        Article(
            id=identifiant,
            code=CodeJuridique.CODE_TRAVAIL,
            numero="L. 9999-8",
            versions=[
                VersionArticle(
                    article_id=identifiant,
                    numero="L. 9999-8",
                    date_debut=date(2000, 1, 1),
                    date_fin=date(2010, 12, 31),
                    texte=texte,
                    statut=StatutVersion.ABROGE,
                    source="fixture-test",
                )
            ],
        )
    ])

    resultat = VerificateurStandard(depot).verifier(
        _citation(
            CodeJuridique.CODE_TRAVAIL,
            "L. 9999-8",
            date(2005, 1, 1),
            extrait="Texte historique applicable",
        )
    )

    assert resultat.statut == StatutVerification.VALIDE


def test_statut_version_inconnu_nest_jamais_valide(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    identifiant = IdentifiantLegifrance(valeur="LEGIARTI000099999997")
    depot.enregistrer([
        Article(
            id=identifiant,
            code=CodeJuridique.CODE_TRAVAIL,
            numero="L. 9999-7",
            versions=[
                VersionArticle(
                    article_id=identifiant,
                    numero="L. 9999-7",
                    date_debut=date(2000, 1, 1),
                    texte="Version avec statut inconnu.",
                    statut=StatutVersion.INCONNU,
                    source="fixture-test",
                )
            ],
        )
    ])

    resultat = VerificateurStandard(depot).verifier(
        _citation(
            CodeJuridique.CODE_TRAVAIL,
            "L. 9999-7",
            date(2005, 1, 1),
            extrait="Version avec statut inconnu",
        )
    )

    assert resultat.statut == StatutVerification.STATUT_VERSION_INCONNU


def test_version_abrogee_sans_date_fin_nest_pas_declaree_valide(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    identifiant = IdentifiantLegifrance(valeur="LEGIARTI000099999996")
    depot.enregistrer([
        Article(
            id=identifiant,
            code=CodeJuridique.CODE_TRAVAIL,
            numero="L. 9999-6",
            versions=[
                VersionArticle(
                    article_id=identifiant,
                    numero="L. 9999-6",
                    date_debut=date(2000, 1, 1),
                    date_fin=None,
                    texte="Version abrogee sans borne de fin connue.",
                    statut=StatutVersion.ABROGE,
                    source="fixture-test",
                )
            ],
        )
    ])

    resultat = VerificateurStandard(depot).verifier(
        _citation(
            CodeJuridique.CODE_TRAVAIL,
            "L. 9999-6",
            date(2005, 1, 1),
            extrait="Version abrogee sans borne de fin",
        )
    )

    assert resultat.statut == StatutVerification.VERSION_INCORRECTE


def test_article_apres_toutes_versions_sans_fin(tmp_path):
    """L'article 1240 est en vigueur sans date de fin."""
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2099, 1, 1),
        extrait=EXTRAIT_1240,
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE


def test_verifier_toutes_retourne_une_liste(tmp_path):
    v = _verificateur(tmp_path)
    citations = [
        _citation(
            CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
            extrait=EXTRAIT_1240,
        ),
        _citation(
            CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(2020, 1, 1),
            extrait=EXTRAIT_L1234_1,
        ),
        _citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1)),
    ]
    resultats = v.verifier_toutes(citations)
    assert len(resultats) == 3
    assert resultats[0].statut == StatutVerification.VALIDE
    assert resultats[1].statut == StatutVerification.VALIDE
    assert resultats[2].statut == StatutVerification.INTROUVABLE


def test_melange_verdicts(tmp_path):
    """On passe un melange de citations et on verifie chaque verdict."""
    v = _verificateur(tmp_path)

    cas = [
        (_citation(
            CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
            extrait=EXTRAIT_1240,
        ), StatutVerification.VALIDE),
        (_citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1)),
         StatutVerification.INTROUVABLE),
        (_citation(CodeJuridique.CODE_CIVIL, "1240", date(1900, 1, 1)),
         StatutVerification.VERSION_INCORRECTE),
        (_citation(
            CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
            extrait="invente totalement",
        ), StatutVerification.TEXTE_DIFFERENT),
        (_citation(CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1)),
         StatutVerification.EXTRAIT_MANQUANT),
    ]

    for citation, attendu in cas:
        res = v.verifier(citation)
        assert res.statut == attendu, f"Attendu {attendu}, obtenu {res.statut}"


def test_extrait_normalise_accents(tmp_path):
    """Un extrait avec accents differents doit quand meme matcher."""
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="TOUT FAIT QUELCONQUE DE L'HOMME",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE


def test_verificateur_suit_article_id_en_cas_de_collision_code_numero(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    id_a = IdentifiantLegifrance(valeur="LEGIARTI000009999991")
    id_b = IdentifiantLegifrance(valeur="LEGIARTI000009999992")
    date_debut = date(2020, 1, 1)
    articles = []
    for identifiant, texte in (
        (id_a, "Texte de la premiere version."),
        (id_b, "Texte officiel propre a la seconde version."),
    ):
        articles.append(Article(
            id=identifiant,
            code=CodeJuridique.CODE_CIVIL,
            numero="1240",
            versions=[VersionArticle(
                article_id=identifiant,
                numero="1240",
                date_debut=date_debut,
                texte=texte,
                statut=StatutVersion.EN_VIGUEUR,
                source="fixture-test",
            )],
        ))
    depot.enregistrer(articles)
    citation = _citation(
        CodeJuridique.CODE_CIVIL,
        "1240",
        date(2021, 1, 1),
        extrait="Texte officiel propre a la seconde version",
    ).model_copy(update={"article_id": id_b.valeur})

    resultat = VerificateurStandard(depot).verifier(citation)

    assert resultat.statut == StatutVerification.VALIDE
    assert resultat.version is not None
    assert resultat.version.article_id == id_b


def test_verificateur_rejette_metadonnees_incoherentes_avec_article_id(tmp_path):
    verificateur = _verificateur(tmp_path)
    citation = _citation(
        CodeJuridique.CODE_TRAVAIL,
        "L. 1234-1",
        date(2024, 1, 1),
        extrait=EXTRAIT_L1234_1,
    ).model_copy(update={"article_id": "LEGIARTI000033020517"})

    resultat = verificateur.verifier(citation)

    assert resultat.statut == StatutVerification.IDENTIFIANT_INCOHERENT


def test_verificateur_id_accepte_le_numero_de_la_version_historique(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    identifiant = IdentifiantLegifrance(valeur="LEGIARTI000009999993")
    depot.enregistrer([
        Article(
            id=identifiant,
            code=CodeJuridique.CODE_TRAVAIL,
            numero="L1234-2",
            versions=[
                VersionArticle(
                    article_id=identifiant,
                    numero="L. 1234-1",
                    date_debut=date(2000, 1, 1),
                    date_fin=date(2010, 12, 31),
                    texte="Ancien texte officiel.",
                    statut=StatutVersion.EN_VIGUEUR,
                    source="fixture-test",
                ),
                VersionArticle(
                    article_id=identifiant,
                    numero="L. 1234-2",
                    date_debut=date(2011, 1, 1),
                    texte="Texte actuel.",
                    statut=StatutVersion.EN_VIGUEUR,
                    source="fixture-test",
                ),
            ],
        )
    ])
    citation = _citation(
        CodeJuridique.CODE_TRAVAIL,
        "L. 1234-1",
        date(2005, 1, 1),
        extrait="Ancien texte officiel",
    ).model_copy(update={"article_id": identifiant.valeur})

    resultat = VerificateurStandard(depot).verifier(citation)

    assert resultat.statut == StatutVerification.VALIDE
    assert resultat.version is not None
    assert resultat.version.numero == "L1234-1"
