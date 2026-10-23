"""Tests du contrat type des scenarios fictifs."""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from beaume.scenario.model import (
    ModeProvenance,
    Montant,
    Provenance,
    Scenario,
)


def _prov_ok(mode="cree"):
    if mode == "cree":
        return Provenance(mode=ModeProvenance.CREE, regle="r")
    if mode == "repris":
        return Provenance(mode=ModeProvenance.REPRIS, source_id="src:x", passage_exact="p")
    if mode == "transforme":
        return Provenance(mode=ModeProvenance.TRANSFORME, source_id="src:x", transformation="t")
    if mode == "calcule":
        return Provenance(mode=ModeProvenance.CALCULE, operation="add", dependances=["a"])
    raise ValueError(mode)


def _scenario_min(amount="25000.00", **overrides):
    base = {
        "schema_version": "0.3",
        "scenario_id": "BEAUME-SC-0002-v1",
        "scenario_version": 1,
        "partition": "dev",
        "domain": "licenciement_contestation",
        "language": "fr",
        "created_at": "2026-10-23",
        "sources": [],
        "actors": [
            {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"],
             "provenance": _prov_ok().model_dump()},
            {"actor_id": "scn:actor:e", "display_name": "E", "roles": ["defendeur"],
             "provenance": _prov_ok().model_dump()},
        ],
        "events": [
            {"event_id": "scn:event:x",
             "date": {"valeur": "2020-01-01", "precision": "jour"},
             "description": "d",
             "actors_impliques": ["scn:actor:s"],
             "provenance": _prov_ok().model_dump()}
        ],
        "documents": [
            {"document_id": "scn:doc:saisine",
             "titre": "t",
             "date": {"valeur": "2026-01-01", "precision": "jour"},
             "nature": "saisine",
             "auteur": "scn:actor:s",
             "assertions": [],
             "contenu": {
                "mode": "texte", "texte": "x",
                "champs": {"MONTANT": {"type": "litteral", "valeur": amount}},
                "declarations": {"MONTANT": "montant"},
            },
             "provenance": _prov_ok().model_dump()}
        ],
        "propositions_juridiques": [],
    }
    base.update(overrides)
    return base


def test_exemple_conforme_se_charge():
    Scenario(**_scenario_min())


def test_champ_obligatoire_absent():
    data = _scenario_min()
    del data["actors"]
    with pytest.raises(ValidationError):
        Scenario(**data)


def test_origine_inconnue_provenance_absente():
    data = _scenario_min()
    del data["actors"][0]["provenance"]
    with pytest.raises(ValidationError):
        Scenario(**data)


def test_provenance_incomplete_mode_repris():
    with pytest.raises(ValidationError):
        Provenance(mode=ModeProvenance.REPRIS)
    with pytest.raises(ValidationError):
        Provenance(mode=ModeProvenance.REPRIS, source_id="src:x")
    with pytest.raises(ValidationError):
        Provenance(mode=ModeProvenance.TRANSFORME, source_id="src:x")
    with pytest.raises(ValidationError):
        Provenance(mode=ModeProvenance.CREE)
    with pytest.raises(ValidationError):
        Provenance(mode=ModeProvenance.CALCULE, operation="add")


def test_type_montant_float_refuse():
    with pytest.raises(ValidationError):
        Montant(valeur=25000.0)


def test_type_montant_chaine_exacte():
    m = Montant(valeur="25000.00")
    assert m.valeur == Decimal("25000.00")


def test_type_montant_negatif_refuse():
    with pytest.raises(ValidationError):
        Montant(valeur="-1.00")


def test_id_prefixe_invalide():
    data = _scenario_min()
    data["actors"][0]["actor_id"] = "actor-1"
    with pytest.raises(ValidationError):
        Scenario(**data)


def test_date_iso_invalide():
    data = _scenario_min()
    data["events"][0]["date"] = {"valeur": "01/01/2020", "precision": "jour"}
    with pytest.raises(ValidationError):
        Scenario(**data)


def test_schema_version_invalide():
    data = _scenario_min()
    data["schema_version"] = "0.1"
    with pytest.raises(ValidationError):
        Scenario(**data)



# --- F-a1 : types de champ (parsing strict) ---

def test_valeur_litterale_extra_rejete():
    from pydantic import ValidationError
    from beaume.scenario.champs import ValeurLitterale
    import pytest
    with pytest.raises(ValidationError):
        ValeurLitterale(type="litteral", valeur="x", extra="y")


def test_attribut_inconnu_rejete():
    import pytest
    from pydantic import ValidationError
    from beaume.scenario.champs import ValeurReference
    with pytest.raises(ValidationError):
        ValeurReference(type="reference", cible="scn:actor:x", attribut="nom")


def test_motif_absence_inconnu_rejete():
    import pytest
    from pydantic import ValidationError
    from beaume.scenario.champs import ValeurAbsente
    with pytest.raises(ValidationError):
        ValeurAbsente(type="absent", motif="peu_importe")


def test_type_champ_inconnu_rejete():
    import pytest
    from pydantic import ValidationError
    from beaume.scenario.model import ContenuDocument
    with pytest.raises(ValidationError):
        ContenuDocument(
            mode="texte", texte="x",
            champs={"X": {"type": "litteral", "valeur": "x"}},
            declarations={"X": "inexistant"},
        )
