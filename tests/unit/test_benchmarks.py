"""Tests des metriques de retrieval et de l'audit structurel des jeux."""
from __future__ import annotations

import json
import random
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.application.analyse_dossier import AnalyseDossier
from beaume.bench.metriques import calculer_rappel, charger_references_dossier
from beaume.legal.model import Citation, CodeJuridique, StatutVerification
from beaume.ports.depot_articles import ResultatRechercheArticle
from scripts.bench_qualite import (
    _ChercheurTrace,
    _calculer_agregats,
    _diagnostic_citations,
    _diagnostic_couverture,
    _diagnostic_recherche,
)
from scripts.generer_dataset_ft import _construire_conversation, _tirer_leurres
from scripts.verifier_dataset import verifier_ligne


def test_metriques_rappel_micro_macro_mrr_et_hit_rate():
    a = ("code_travail", "L1233-3")
    b = ("code_travail", "L1233-4")
    c = ("code_travail", "L1233-5")
    d = ("code_travail", "L1233-6")

    resultat = calculer_rappel(
        references=[{a, b}, {c}],
        classements=[[a, d], [d, c]],
        k_values=(1, 2),
    )

    assert resultat["n_requetes"] == 2
    assert resultat["n_references"] == 3
    assert resultat["mrr"] == pytest.approx(0.75)
    assert resultat["par_k"]["1"]["rappel_micro"] == pytest.approx(1 / 3)
    assert resultat["par_k"]["1"]["rappel_macro"] == pytest.approx(0.25)
    assert resultat["par_k"]["1"]["taux_requetes_avec_au_moins_un_hit"] == pytest.approx(0.5)
    assert resultat["par_k"]["2"]["rappel_micro"] == pytest.approx(2 / 3)
    assert resultat["par_k"]["2"]["rappel_macro"] == pytest.approx(0.75)


def test_metriques_dedoublonnent_le_classement_avant_le_rang():
    a = ("code_travail", "L1233-3")
    b = ("code_travail", "L1233-4")

    resultat = calculer_rappel([{b}], [[a, a, b]], k_values=(1, 2))

    assert resultat["mrr"] == pytest.approx(0.5)
    assert resultat["par_k"]["1"]["rappel_micro"] == 0.0
    assert resultat["par_k"]["2"]["rappel_micro"] == 1.0


def test_references_exigent_un_code_pour_eviter_les_collisions():
    with pytest.raises(ValueError, match="Code absent"):
        charger_references_dossier({"id": "sans-code", "must_cite": ["1240"]})


def test_audit_dataset_valide_le_contrat_article_id_de_production():
    fait = "Mon employeur a supprime mon poste et m'a convoque."
    cible = {
        "article_id": "LEGIARTI000000000001",
        "code": "code_travail",
        "numero": "L1233-3",
        "texte": "Le licenciement pour motif economique est effectue par un employeur.",
    }
    leurre = {
        "article_id": "LEGIARTI000000000002",
        "code": "code_travail",
        "numero": "L1233-4",
        "texte": "Un autre texte juridique public pour le test.",
    }
    ligne = _construire_conversation(
        fait, [leurre, cible], cible, date(2025, 1, 1),
    )
    resultat = verifier_ligne(
        ligne,
        1,
        {
            "id": "positif-1",
            "type": "positif_synthetique_non_verifie",
            "statut": "genere_auto_a_revoir",
            "article_id_cible": cible["article_id"],
            "article_ids_candidats": [leurre["article_id"], cible["article_id"]],
        },
    )

    assert resultat["erreurs_structure"] == []
    assert resultat["n_candidats"] == 2
    assert resultat["n_citations"] == 1
    assert resultat["controle_pertinence_juridique"] == "non_effectue"
    assert "pertinence juridique non validee par un juriste" in resultat["avertissements"]
    reponse = json.loads(ligne["conversations"][2]["value"])
    assert set(reponse) == {"contexte", "citations"}


def test_audit_rejette_un_article_id_absent_des_candidats():
    fait = "Mon employeur a supprime mon poste."
    cible = {
        "article_id": "LEGIARTI000000000001",
        "code": "code_travail",
        "numero": "L1233-3",
        "texte": "Texte public suffisamment long pour ce test.",
    }
    ligne = _construire_conversation(fait, [cible], cible, date(2025, 1, 1))
    reponse = json.loads(ligne["conversations"][2]["value"])
    reponse["citations"][0]["article_id"] = "LEGIARTI_INVENTE"
    ligne["conversations"][2]["value"] = json.dumps(reponse)

    resultat = verifier_ligne(
        ligne,
        1,
        {
            "type": "positif_synthetique_non_verifie",
            "statut": "genere_auto_a_revoir",
            "article_id_cible": cible["article_id"],
            "article_ids_candidats": [cible["article_id"]],
        },
    )

    assert any("absent des candidats" in erreur for erreur in resultat["erreurs_structure"])


def test_exemple_hors_domaine_peut_apprendre_la_reponse_vide():
    cible = {
        "article_id": "x",
        "code": "code_travail",
        "numero": "L. 1233-3",
        "texte": "Texte public d'exemple suffisamment long.",
    }
    ligne = _construire_conversation(
        "Je cherche une recette de soupe.",
        [cible],
        None,
        date(2025, 1, 1),
    )

    resultat = verifier_ligne(
        ligne,
        1,
        {"type": "hors_domaine_sans_reference_juridique", "statut": "genere_auto_a_revoir"},
    )

    cible_json = json.loads(ligne["conversations"][2]["value"])
    assert cible_json["citations"] == []
    assert resultat["erreurs_structure"] == []


def test_negatif_juridique_est_isole_et_signale_comme_non_verifie():
    cible_cachee = {
        "article_id": "LEGIARTI000000000010",
        "code": "code_travail",
        "numero": "L1233-3",
        "texte": "Texte cible masque pour ce test.",
    }
    candidat = {
        "article_id": "LEGIARTI000000000011",
        "code": "code_travail",
        "numero": "L1233-4",
        "texte": "Texte leurre visible dans le prompt.",
    }
    ligne = _construire_conversation(
        "Fait juridique synthetique a verifier.",
        [candidat],
        None,
        date(2025, 1, 1),
    )

    resultat = verifier_ligne(
        ligne,
        1,
        {
            "type": "juridique_sans_candidat_non_verifie",
            "statut": "genere_auto_a_revoir",
            "article_id_source_masque": cible_cachee["article_id"],
            "article_ids_candidats": [candidat["article_id"]],
        },
    )

    assert resultat["erreurs_structure"] == []
    assert any("ne pas l'utiliser pour entrainer" in a for a in resultat["avertissements"])


def test_tirage_leurres_exclut_la_meme_reference_normalisee():
    cible = {
        "article_id": "id-cible",
        "code": "code_travail",
        "numero": "L. 1233-3",
        "texte": "Texte cible.",
    }
    doublon = {
        "article_id": "id-doublon",
        "code": "code_travail",
        "numero": "L1233-3",
        "texte": "Meme article sous une autre forme.",
    }
    autre = {
        "article_id": "id-autre",
        "code": "code_travail",
        "numero": "L1233-4",
        "texte": "Autre texte.",
    }

    leurres = _tirer_leurres(cible, [cible, doublon, autre], 1, random.Random(3))

    assert [article["article_id"] for article in leurres] == ["id-autre"]


def test_depot_lecture_seule_interdit_les_ecritures(tmp_path):
    chemin = tmp_path / "legi.sqlite"
    depot = DepotSQLite(chemin)
    depot._conn.close()

    lecture_seule = DepotSQLite(chemin, lecture_seule=True)
    try:
        assert lecture_seule.compter() == 0
        with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
            lecture_seule.vider()
    finally:
        lecture_seule._conn.close()


def test_depot_lecture_seule_ne_cree_pas_une_base_absente(tmp_path):
    chemin = tmp_path / "absente.sqlite"

    with pytest.raises(FileNotFoundError):
        DepotSQLite(chemin, lecture_seule=True)
    assert not chemin.exists()


def test_diagnostic_couverture_retrieval_separe_du_resultat_llm():
    attendues = {
        ("code_travail", "L1233-2"),
        ("code_travail", "L1233-1"),
    }
    candidates = {("code_travail", "L1233-2")}

    diagnostic = _diagnostic_couverture(attendues, candidates)

    assert diagnostic["references_must_cite_dans_candidats"] == [
        ["code_travail", "L1233-2"]
    ]
    assert diagnostic["references_must_cite_absentes_des_candidats"] == [
        ["code_travail", "L1233-1"]
    ]
    assert diagnostic["rappel_retrieval_must_cite"] == pytest.approx(0.5)


def test_diagnostic_recherche_conserve_les_candidats_fts5_et_ceux_transmis():
    hit_present = ResultatRechercheArticle(
        article_id="LEGIARTI000000000001",
        code="code_travail",
        numero="L. 1233-2",
        extrait="extrait",
        score=1.0,
    )
    hit_sans_version = ResultatRechercheArticle(
        article_id="LEGIARTI000000000002",
        code="code_travail",
        numero="L. 1233-1",
        extrait="extrait",
        score=0.5,
    )

    class FauxChercheur:
        def chercher(self, texte, limite=5):
            return [hit_present, hit_sans_version]

    class FauxDepot:
        def trouver_par_id(self, article_id, date_reference):
            numero = "L1233-2" if article_id.endswith("1") else "L1233-1"
            a_une_version = article_id.endswith("1")
            return SimpleNamespace(
                id=SimpleNamespace(valeur=article_id),
                code=SimpleNamespace(value="code_travail"),
                numero=numero,
                version_a=lambda d: (
                    SimpleNamespace(numero=numero) if a_une_version else None
                ),
            )

    traceur = _ChercheurTrace(FauxChercheur())
    traceur.chercher("chunk 1", limite=5)
    analyseur = AnalyseDossier(
        registre=MagicMock(),
        chercheur=traceur,
        generateur=MagicMock(),
        depot=FauxDepot(),
        limite_candidats=1,
    )
    pipeline = SimpleNamespace(
        analyseur=analyseur,
        depot=FauxDepot(),
    )

    diagnostic = _diagnostic_recherche(
        pipeline,
        date(2025, 1, 1),
        {
            ("code_travail", "L1233-2"),
            ("code_travail", "L1233-1"),
        },
    )

    assert diagnostic["n_appels_recherche"] == 1
    assert diagnostic["limite_candidats_total"] == 1
    assert len(diagnostic["candidats_fts5_par_chunk"][0]["candidats_fts5"]) == 2
    assert diagnostic["candidats_transmis_au_llm"] == [
        ["code_travail", "L1233-2"]
    ]
    assert diagnostic["rappel_retrieval_must_cite"] == pytest.approx(0.5)


def test_diagnostic_citations_indique_statut_et_presence_candidate():
    citation = Citation(
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L. 1233-3",
        date_reference=date(2025, 1, 1),
        extrait="texte",
    )
    verification = SimpleNamespace(
        citation=citation,
        statut=StatutVerification.TEXTE_DIFFERENT,
        est_valide=False,
    )
    candidat = ("code_travail", "L1233-3")

    details, statuts = _diagnostic_citations(
        SimpleNamespace(verifications=[verification]), {candidat},
    )

    assert details == [{
        "code": "code_travail",
        "numero": "L. 1233-3",
        "statut_verification": "texte_different",
        "est_valide": False,
        "article_dans_candidats": True,
        "extrait_fourni": True,
    }]
    assert statuts == {"texte_different": 1}


def test_diagnostic_citations_ne_plante_pas_sur_un_numero_vide():
    citation = Citation(
        code=CodeJuridique.CODE_TRAVAIL,
        numero="",
        date_reference=date(2025, 1, 1),
        extrait="texte",
    )
    verification = SimpleNamespace(
        citation=citation,
        statut=StatutVerification.NUMERO_MANQUANT,
        est_valide=False,
    )

    details, statuts = _diagnostic_citations(
        SimpleNamespace(verifications=[verification]), set(),
    )

    assert details[0]["numero"] == ""
    assert details[0]["article_dans_candidats"] is False
    assert statuts == {"numero_manquant": 1}


def test_agregats_separent_recall_retrieval_des_citations_valides():
    resultats = [{
        "statut_execution": "ok",
        "references": [["code_travail", "L1233-2"]],
        "references_valides_trouvees": [],
        "references_must_cite_dans_candidats": [["code_travail", "L1233-2"]],
        "statuts_citations": {"texte_different": 1},
        "duree_s": 1.0,
    }]

    metriques = _calculer_agregats(resultats)

    assert metriques["rappel_micro_retrieval_must_cite"] == 1.0
    assert metriques["rappel_micro_must_cite"] == 0.0
    assert metriques["statuts_citations"] == {"texte_different": 1}
