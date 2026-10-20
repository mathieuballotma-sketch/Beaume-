"""Tests du rapprochement citation -> version de loi pour l'entrainement."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from scripts.construire_dataset_entrainement import _construire_paires, _resoudre_article


def _version(
    article_id: str,
    code: str,
    texte: str,
    debut: str = "2010-01-01",
    fin: str | None = None,
) -> dict:
    return {
        "article_id": article_id,
        "code": code,
        "numero": "L. 1234-1",
        "texte": texte,
        "date_debut": debut,
        "date_fin": fin,
    }


def test_resout_article_par_numero_code_et_date():
    articles = {
        "L1234-1": [
            _version("travail-1", "code_travail", "Texte du travail"),
            _version("conso-1", "code_consommation", "Texte consommation"),
        ]
    }

    version, erreur = _resoudre_article(
        articles,
        {"code": "code_consommation", "numero": "L. 1234-1"},
        date(2020, 6, 1),
    )

    assert erreur is None
    assert version is not None
    assert version["article_id"] == "conso-1"


def test_refuse_numero_ambigu_sans_code():
    articles = {
        "L1234-1": [
            _version("travail-1", "code_travail", "Texte du travail"),
            _version("conso-1", "code_consommation", "Texte consommation"),
        ]
    }

    version, erreur = _resoudre_article(articles, "L1234-1", date(2020, 6, 1))

    assert version is None
    assert erreur == "reference_ambigue"


def test_refuse_version_non_applicable_a_la_date_du_fait():
    articles = {
        "L1234-1": [
            _version("travail-1", "code_travail", "Version recente", debut="2022-01-01")
        ]
    }

    version, erreur = _resoudre_article(articles, "L1234-1", date(2020, 6, 1))

    assert version is None
    assert erreur == "aucune_version_a_la_date"


def test_construire_paires_ignore_les_references_ambigues(tmp_path):
    faits = tmp_path / "faits.jsonl"
    faits.write_text(
        json.dumps({
            "id": "fait-1",
            "faits_client": "Un fait synthétique suffisamment long.",
            "articles": ["L1234-1"],
            "date": "2020-06-01",
        }) + "\n",
        encoding="utf-8",
    )
    articles = {
        "L1234-1": [
            _version("travail-1", "code_travail", "Texte du travail"),
            _version("conso-1", "code_consommation", "Texte consommation"),
        ]
    }

    paires, stats = _construire_paires(faits, articles, max_par_fait=3)

    assert paires == []
    assert stats["n_references_ambigues"] == 1
    assert stats["n_paires"] == 0


def test_construire_paires_enregistre_le_code_et_une_version_datee(tmp_path):
    faits = tmp_path / "faits.jsonl"
    faits.write_text(
        json.dumps({
            "id": "fait-2",
            "faits_client": "Un fait synthétique suffisamment long.",
            "articles": [{"code": "code_travail", "numero": "L. 1234-1"}],
            "date": "2020-06-01",
        }) + "\n",
        encoding="utf-8",
    )
    articles = {
        "L1234-1": [
            _version("travail-1", "code_travail", "Texte applicable", debut="2010-01-01", fin="2020-12-31"),
            _version("travail-1", "code_travail", "Texte futur", debut="2021-01-01"),
        ]
    }

    paires, stats = _construire_paires(faits, articles, max_par_fait=3)

    assert len(paires) == 1
    assert paires[0]["article_id"] == "travail-1"
    assert paires[0]["code"] == "code_travail"
    assert paires[0]["positive"] == "Texte applicable"
    assert paires[0]["date_fait"] == date(2020, 6, 1)
    assert stats["n_manquants"] == 0


def test_construire_paires_ignore_une_ligne_json_non_objet(tmp_path):
    faits = tmp_path / "faits.jsonl"
    faits.write_text("null\n", encoding="utf-8")

    paires, stats = _construire_paires(faits, {}, max_par_fait=3)

    assert paires == []
    assert stats["n_lignes_ignorees"] == 1


def test_telecharger_corpus_v2_echoue_explicitement_tant_que_non_implemente():
    racine = Path(__file__).resolve().parents[2]
    script = racine / "scripts" / "telecharger_corpus_v2.py"

    resultat = subprocess.run(
        [sys.executable, str(script)],
        cwd=racine,
        capture_output=True,
        text=True,
        check=False,
    )

    assert resultat.returncode == 2
    assert "integration AgentPublic/legi non implementee" in resultat.stderr
