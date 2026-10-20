from __future__ import annotations

import json
import sqlite3
import sys

from scripts import generer_dataset_ft
from scripts.generer_dataset_ft import _contient_reference_cible, _sha256_ligne
from scripts.verifier_dataset import verifier_ligne


def _creer_corpus_minimal(chemin):
    with sqlite3.connect(chemin) as conn:
        conn.executescript(
            """
            CREATE TABLE articles (id TEXT PRIMARY KEY, code TEXT, numero TEXT);
            CREATE TABLE versions (
                article_id TEXT, numero TEXT, date_debut TEXT, date_fin TEXT,
                texte TEXT, statut TEXT
            );
            """
        )
        for index in range(12):
            article_id = f"LEGIARTI000000000{index:03d}"
            numero = f"L1234-{index + 1}"
            texte = (
                f"Le texte juridique public numero {index + 1} decrit une regle "
                "applicable dans la situation de test et comporte assez de contenu."
            )
            conn.execute(
                "INSERT INTO articles VALUES (?, ?, ?)",
                (article_id, "code_travail", numero),
            )
            conn.execute(
                "INSERT INTO versions VALUES (?, ?, ?, ?, ?, ?)",
                (article_id, numero, "2020-01-01", None, texte, "en_vigueur"),
            )


def test_main_separe_positifs_hors_domaine_et_pseudo_negatifs(tmp_path, monkeypatch):
    base = tmp_path / "legi.sqlite"
    _creer_corpus_minimal(base)
    sortie_embedder = tmp_path / "train_embedder.jsonl"
    sortie_llm = tmp_path / "train_llm.jsonl"
    sortie_revue = tmp_path / "sans_candidat_a_revoir.jsonl"
    manifeste = tmp_path / "manifest.json"
    monkeypatch.setattr(
        generer_dataset_ft,
        "generer_fait",
        lambda texte, numero, modele: "Un salarie rencontre un probleme professionnel.",
    )
    monkeypatch.setattr(sys, "argv", [
        "generer_dataset_ft.py",
        "--base", str(base),
        "--n", "10",
        "--graine", "9",
        "--ratio-hors-domaine", "0.1",
        "--ratio-sans-candidat", "0.1",
        "--leurres", "2",
        "--sortie-embedder", str(sortie_embedder),
        "--sortie-llm", str(sortie_llm),
        "--sortie-sans-candidat", str(sortie_revue),
        "--manifeste", str(manifeste),
    ])

    assert generer_dataset_ft.main() == 0

    rows_llm = [json.loads(x) for x in sortie_llm.read_text().splitlines()]
    rows_revue = [json.loads(x) for x in sortie_revue.read_text().splitlines()]
    rows_embedder = [json.loads(x) for x in sortie_embedder.read_text().splitlines()]
    meta = json.loads(manifeste.read_text())

    assert len(rows_embedder) == 8
    assert len(rows_llm) == 9  # huit positifs + un hors domaine
    assert len(rows_revue) == 1  # conserve hors du train le pseudo-negatif legal
    assert len(meta["exemples_llm"]) == len(rows_llm)
    assert len(meta["exemples_llm_sans_candidat_a_revoir"]) == len(rows_revue)

    for index, (ligne, metadata) in enumerate(
        zip(rows_llm, meta["exemples_llm"]), start=1,
    ):
        resultat = verifier_ligne(
            ligne, index, metadata, sha256_ligne=_sha256_ligne(ligne),
        )
        assert resultat["erreurs_structure"] == []
    resultat_revue = verifier_ligne(
        rows_revue[0],
        1,
        meta["exemples_llm_sans_candidat_a_revoir"][0],
        sha256_ligne=_sha256_ligne(rows_revue[0]),
    )
    assert resultat_revue["erreurs_structure"] == []
    assert resultat_revue["avertissements"]
    resultat_modifie = verifier_ligne(
        rows_revue[0],
        1,
        meta["exemples_llm_sans_candidat_a_revoir"][0],
        sha256_ligne="empreinte-differente",
    )
    assert "le contenu de la ligne ne correspond pas au manifeste" in (
        resultat_modifie["erreurs_structure"]
    )


def test_filtre_les_faits_qui_revelent_le_numero_cible():
    assert _contient_reference_cible(
        "Mon dossier concerne l'article L. 1234-1.",
        "L1234-1",
    )
    assert _contient_reference_cible(
        "La reference L1234-1 a ete mentionnee.",
        "L1234-1",
    )
    assert not _contient_reference_cible(
        "Mon salaire est de 1240 euros.",
        "1240",
    )
    assert _contient_reference_cible(
        "Je conteste l'article 1240.",
        "1240",
    )
