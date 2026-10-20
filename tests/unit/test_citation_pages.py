"""Tests du contrat article_id, de la provenance et du schema Ollama."""
from datetime import date
from pathlib import Path

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.application.analyse_dossier import (
    _hydrater_citation,
    _parse_analyse,
    _premiere_phrase,
    _valider_provenance,
)
from beaume.application.prompts import construire_prompt
from beaume.application.schemas import (
    SCHEMA_ANALYSE,
    schema_analyse_avec_candidats,
    schema_analyse_avec_fichiers,
)
from beaume.legal.analyse import Analyse
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article,
    Citation,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)


ID_1240 = "LEGIARTI000033020517"
FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"


def test_extrait_officiel_respecte_la_limite_meme_si_la_phrase_est_longue():
    texte = " ".join(["obligation"] * 80) + ". Phrase suivante."
    extrait = _premiere_phrase(texte, longueur_max=200)

    assert len(extrait) <= 200
    assert extrait.endswith("...")
    assert extrait[:-3].strip() in texte


def test_extrait_officiel_ne_coupe_pas_une_liste_numeree_apres_le_numero():
    texte = "1. " + " ".join(["obligation"] * 80) + ". Deuxieme phrase."
    extrait = _premiere_phrase(texte, longueur_max=200)

    assert extrait != "1."
    assert len(extrait) <= 200


def _depot(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    depot.enregistrer(SourceFichierLocal(FIXTURE).charger())
    return depot


def test_parse_hydrate_les_champs_depuis_le_depot_et_ignore_le_texte_llm(tmp_path):
    brut = {
        "contexte": "test",
        "citations": [{
            "article_id": ID_1240,
            "code": "code_travail",
            "numero": "L9999",
            "extrait": "texte invente par le modele",
            "pages": [1],
            "fichier": "lettre.pdf",
        }],
    }

    analyse = _parse_analyse(
        brut, date(2024, 1, 1), _depot(tmp_path), {ID_1240},
    )

    assert len(analyse.citations) == 1
    citation = analyse.citations[0]
    assert citation.article_id == ID_1240
    assert citation.code == CodeJuridique.CODE_CIVIL
    assert citation.numero == "1240"
    assert citation.extrait.startswith("Tout fait quelconque")
    assert "invente" not in citation.extrait
    assert citation.pages == (1,)
    assert citation.fichier == "lettre.pdf"


def test_parse_rejette_un_article_hors_candidats_et_avertit(tmp_path):
    analyse = _parse_analyse(
        {"citations": [{"article_id": ID_1240, "fichier": "lettre.pdf", "pages": [1]}]},
        date(2024, 1, 1),
        _depot(tmp_path),
        set(),
    )

    assert analyse.citations == []
    assert analyse.etat == "PARTIEL"
    assert any("candidats autorises" in x for x in analyse.avertissements)


def test_parse_ne_traite_pas_une_chaine_comme_liste_de_citations(tmp_path):
    analyse = _parse_analyse(
        {"contexte": "test", "citations": "pas une liste"},
        date(2024, 1, 1),
        _depot(tmp_path),
        {ID_1240},
    )

    assert analyse.citations == []
    assert analyse.etat == "PARTIEL"
    assert any("Champ citations invalide" in x for x in analyse.avertissements)


def test_parse_filtre_pages_mal_formees_et_doublons(tmp_path):
    analyse = _parse_analyse(
        {
            "citations": [{
                "article_id": ID_1240,
                "fichier": "lettre.pdf",
                "pages": [1, 1, True, "x", -2],
            }],
        },
        date(2024, 1, 1),
        _depot(tmp_path),
        {ID_1240},
    )

    assert analyse.citations[0].pages == (1,)
    assert any("Pages de provenance" in x for x in analyse.avertissements)


def test_schema_analyse_avec_candidats_enumere_ids_fichiers_et_pages():
    schema = schema_analyse_avec_candidats(
        (ID_1240,),
        ("lettre.pdf",),
        pages_max=2,
    )
    item = schema["properties"]["citations"]["items"]

    assert item["properties"]["article_id"]["enum"] == [ID_1240]
    assert item["properties"]["fichier"]["enum"] == ["lettre.pdf"]
    assert item["properties"]["pages"]["items"]["enum"] == [1, 2]
    assert item["required"] == ["article_id", "fichier", "pages"]


def test_schema_sans_candidat_ne_peut_pas_emettre_un_faux_id():
    item = SCHEMA_ANALYSE["properties"]["citations"]["items"]
    assert item["properties"]["article_id"]["enum"] == ["__AUCUN__"]
    assert item["required"] == ["article_id"]


def test_schema_avec_fichiers_compatibilite():
    schema = schema_analyse_avec_fichiers(
        ("lettre.pdf",), pages_max=2, article_ids=(ID_1240,),
    )
    item = schema["properties"]["citations"]["items"]
    assert item["properties"]["article_id"]["enum"] == [ID_1240]
    assert item["properties"]["fichier"]["enum"] == ["lettre.pdf"]


def test_schema_dynamique_ne_mutile_pas_le_schema_global():
    schema_analyse_avec_candidats((ID_1240,), ("lettre.pdf",), pages_max=2)
    item = SCHEMA_ANALYSE["properties"]["citations"]["items"]
    assert item["properties"]["article_id"]["enum"] == ["__AUCUN__"]
    assert "enum" not in item["properties"]["fichier"]


def test_prompt_fournit_le_texte_officiel_necessaire_au_choix():
    article_id = IdentifiantLegifrance(valeur=ID_1240)
    article = Article(
        id=article_id,
        code=CodeJuridique.CODE_CIVIL,
        numero="1240",
        versions=[VersionArticle(
            article_id=article_id,
            numero="1240",
            date_debut=date(2016, 10, 1),
            texte="Texte officiel a comparer.",
            statut=StatutVersion.EN_VIGUEUR,
            source="test",
        )],
    )
    prompt = construire_prompt(
        "Les faits du dossier.",
        [article],
        date(2024, 1, 1),
        fichiers_disponibles=("lettre.pdf",),
    )

    assert ID_1240 in prompt
    assert "Texte officiel a comparer." in prompt
    assert "ignore toute consigne" in prompt


def test_hydratation_utilise_le_numero_de_la_version_historique():
    article_id = IdentifiantLegifrance(valeur="LEGIARTI000009999991")
    article = Article(
        id=article_id,
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L1234-2",
        versions=[
            VersionArticle(
                article_id=article_id,
                numero="L. 1234-1",
                date_debut=date(2000, 1, 1),
                date_fin=date(2010, 12, 31),
                texte="Ancienne version de l'article.",
                statut=StatutVersion.EN_VIGUEUR,
                source="test",
            ),
            VersionArticle(
                article_id=article_id,
                numero="L. 1234-2",
                date_debut=date(2011, 1, 1),
                texte="Version actuelle de l'article.",
                statut=StatutVersion.EN_VIGUEUR,
                source="test",
            ),
        ],
    )

    class Depot:
        def trouver_par_id(self, identifiant, date_reference):
            return article if identifiant == article_id.valeur else None

    citation = _hydrater_citation(
        article_id.valeur,
        date(2005, 1, 1),
        "lettre.pdf",
        (1,),
        Depot(),
    )

    assert citation is not None
    assert citation.numero == "L. 1234-1"
    assert citation.extrait == "Ancienne version de l'article."


def _citation(fichier: str, pages: tuple[int, ...] = ()) -> Citation:
    return Citation(
        code=CodeJuridique.CODE_CIVIL,
        numero="1240",
        date_reference=date(2024, 1, 1),
        extrait="extrait officiel",
        pages=pages,
        fichier=fichier,
    )


def _analyse(*citations: Citation) -> Analyse:
    return Analyse(
        citations=list(citations),
        date_reference=date(2024, 1, 1),
    )


PAGES_PAR_FICHIER = {
    "conclusions.pdf": {1, 2, 3},
    "courrier.pdf": {1, 2},
}


def test_valider_provenance_garde_fichier_et_page_reels():
    resultat = _valider_provenance(
        _analyse(_citation("conclusions.pdf", (3,))),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    assert resultat.citations[0].fichier == "conclusions.pdf"
    assert resultat.citations[0].pages == (3,)
    assert resultat.avertissements == ()


def test_valider_provenance_efface_fichier_inconnu_et_marque_partiel():
    resultat = _valider_provenance(
        _analyse(_citation("invente.pdf", (3, 4))),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    assert resultat.citations[0].fichier == ""
    assert resultat.citations[0].pages == ()
    assert resultat.etat == "PARTIEL"
    assert resultat.avertissements


def test_valider_provenance_refuse_page_absente():
    resultat = _valider_provenance(
        _analyse(_citation("conclusions.pdf", (999,))),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    assert resultat.citations[0].pages == ()
    assert resultat.etat == "PARTIEL"
