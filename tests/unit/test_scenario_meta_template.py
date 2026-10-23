"""Tests des metas de template (F-b3a)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from beaume.scenario.meta_template import (
    ChampMeta,
    MetaTemplate,
    charger_meta,
    nom_meta_pour,
)

RACINE = Path(__file__).resolve().parents[2]
STRUCT = RACINE / "data" / "scenarios" / "structures"

TEMPLATES = [
    "saisine_prud_hommes.md",
    "conclusions_prud.md",
    "contrat_pret.md",
    "assignation_tj.md",
]


@pytest.mark.parametrize("nom", TEMPLATES)
def test_meta_present_et_chargeable(nom):
    meta = charger_meta(STRUCT / f"{nom}.meta.json")
    assert meta.template == nom
    assert meta.schema_meta == "1"
    assert meta.champs


@pytest.mark.parametrize("nom", TEMPLATES)
def test_meta_parite_avec_balises(nom):
    from beaume.scenario.validateur import _RE_BALISE
    balises = set(_RE_BALISE.findall((STRUCT / nom).read_text(encoding="utf-8")))
    meta = charger_meta(STRUCT / f"{nom}.meta.json")
    assert set(meta.champs) == balises


def test_contrat_pret_balise_corrigee():
    contenu = (STRUCT / "contrat_pret.md").read_text(encoding="utf-8")
    assert "[NOM_PREtEUR]" not in contenu
    assert "[NOM_PRETEUR]" in contenu
    assert "Le Prêteur consent" in contenu
    assert "La Banque consent" not in contenu


def test_assignation_tj_renomme_et_modernise():
    assert (STRUCT / "assignation_tj.md").is_file()
    assert not (STRUCT / "assignation_tgi.md").exists()
    contenu = (STRUCT / "assignation_tj.md").read_text(encoding="utf-8")
    assert "TRIBUNAL JUDICIAIRE" in contenu
    assert "TRIBUNAL DE GRANDE INSTANCE" not in contenu
    assert "Tribunal de Grande Instance" not in contenu
    assert "[ANNEE]" not in contenu
    assert "[DATE_JOUR]" not in contenu


def test_meta_extra_refuse():
    with pytest.raises(ValidationError):
        MetaTemplate(
            schema_meta="1",
            template="x.md",
            champs={"A": {"type": "texte", "obligatoire": True}},
            intrus=1,
        )


def test_champ_meta_extra_refuse():
    with pytest.raises(ValidationError):
        ChampMeta(type="texte", obligatoire=True, intrus=1)


def test_champ_meta_type_inconnu_refuse():
    with pytest.raises(ValidationError):
        ChampMeta(type="invente", obligatoire=True)


def test_champ_meta_obligatoire_non_bool_refuse():
    with pytest.raises(ValidationError):
        ChampMeta(type="texte", obligatoire="oui")


def test_meta_vide_refuse():
    with pytest.raises(ValidationError):
        MetaTemplate(schema_meta="1", template="x.md", champs={})


def test_meta_schema_version_inconnu_refuse():
    with pytest.raises(ValidationError):
        MetaTemplate(
            schema_meta="2",
            template="x.md",
            champs={"A": {"type": "texte", "obligatoire": True}},
        )


def test_charger_meta_json_invalide(tmp_path):
    chemin = tmp_path / "x.md.meta.json"
    chemin.write_text("{not json", encoding="utf-8")
    with pytest.raises(Exception):
        charger_meta(chemin)


def test_nom_meta_pour():
    assert nom_meta_pour(Path("a/b/c.md")).name == "c.md.meta.json"


def test_verifier_templates_meta_absent_echoue(tmp_path):
    """Template sans meta : ECHOUE avec motif [absent]."""
    from beaume.scenario.model import Scenario
    from beaume.scenario.validateur import verifier_templates
    (tmp_path / "data" / "scenarios" / "structures").mkdir(parents=True)
    (tmp_path / "data" / "scenarios" / "structures" / "t.md").write_text(
        "[A]", encoding="utf-8"
    )
    sc = Scenario(
        schema_version="0.3", scenario_id="BEAUME-SC-0002",
        scenario_version=1, partition="dev", domain="d",
        language="fr", created_at="2026-10-23", sources=[],
        actors=[
            {"actor_id": "scn:actor:s", "display_name": "S",
             "roles": ["demandeur"],
             "provenance": {"mode": "cree", "regle": "r", "parametres": {}}},
            {"actor_id": "scn:actor:e", "display_name": "E",
             "roles": ["defendeur"],
             "provenance": {"mode": "cree", "regle": "r", "parametres": {}}},
        ],
        events=[{
            "event_id": "scn:event:e",
            "date": {"valeur": "2020-01-01", "precision": "jour"},
            "description": "d", "actors_impliques": ["scn:actor:s"],
            "provenance": {"mode": "cree", "regle": "r", "parametres": {}},
        }],
        documents=[{
            "document_id": "scn:doc:d", "titre": "t",
            "date": {"valeur": "2026-01-01", "precision": "jour"},
            "nature": "x", "auteur": "scn:actor:s", "assertions": [],
            "contenu": {"mode": "template",
                        "chemin": "data/scenarios/structures/t.md",
                        "champs": {"A": {"type": "litteral", "valeur": "x"}},
                        "declarations": {"A": "texte"}},
            "provenance": {"mode": "cree", "regle": "r", "parametres": {}},
        }],
        propositions_juridiques=[],
    )
    c = verifier_templates(sc, tmp_path)
    assert c.resultat.value == "echoue"
    assert "[absent]" in c.motif
