"""Tests du resolveur commun."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from beaume.scenario.calculs import ResultatCalcul
from beaume.scenario.champs import AttributReference, ValeurReference
from beaume.scenario.model import Calcul, Scenario
from beaume.scenario.resolution import ErreurResolution, resoudre_reference


def _prov():
    return {"mode": "cree", "regle": "r", "parametres": {}}


def _scenario(calculs=None):
    return Scenario(
        schema_version="0.3",
        scenario_id="BEAUME-SC-0002-v1",
        scenario_version=1,
        partition="dev",
        domain="d",
        language="fr",
        created_at="2026-10-23",
        sources=[],
        actors=[
            {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"], "provenance": _prov()},
            {"actor_id": "scn:actor:e", "display_name": "E", "roles": ["defendeur"], "provenance": _prov()},
        ],
        events=[{"event_id": "scn:event:x",
                 "date": {"valeur": "2020-01-01", "precision": "jour"},
                 "description": "d",
                 "actors_impliques": ["scn:actor:s"],
                 "provenance": _prov()}],
        documents=[{"document_id": "scn:doc:saisine", "titre": "t",
                    "date": {"valeur": "2026-01-01", "precision": "jour"},
                    "nature": "saisine", "auteur": "scn:actor:s",
                    "assertions": [], "contenu": {"mode": "texte", "texte": "x"},
                    "provenance": _prov()}],
        propositions_juridiques=[],
        calculs=calculs or [],
    )


def test_resolution_actor_display_name():
    ref = ValeurReference(type="reference", cible="scn:actor:s",
                          attribut=AttributReference.DISPLAY_NAME)
    assert resoudre_reference(ref, _scenario()) == "S"


def test_resolution_event_date():
    ref = ValeurReference(type="reference", cible="scn:event:x",
                          attribut=AttributReference.DATE)
    assert resoudre_reference(ref, _scenario()) == date(2020, 1, 1)


def test_resolution_event_description():
    ref = ValeurReference(type="reference", cible="scn:event:x",
                          attribut=AttributReference.DESCRIPTION)
    assert resoudre_reference(ref, _scenario()) == "d"


def test_resolution_doc_date():
    ref = ValeurReference(type="reference", cible="scn:doc:saisine",
                          attribut=AttributReference.DATE)
    assert resoudre_reference(ref, _scenario()) == date(2026, 1, 1)


def test_resolution_calc_decimal():
    sc = _scenario(calculs=[Calcul(
        calcul_id="scn:calc:a", operation="somme_montants",
        arguments=["1", "1"],
    )])
    ref = ValeurReference(type="reference", cible="scn:calc:a",
                          attribut=AttributReference.VALEUR)
    assert resoudre_reference(ref, sc) == Decimal("2")


def test_resolution_calc_avec_resultats_precalcules():
    sc = _scenario(calculs=[Calcul(
        calcul_id="scn:calc:a", operation="somme_montants",
        arguments=["1", "1"],
    )])
    ref = ValeurReference(type="reference", cible="scn:calc:a",
                          attribut=AttributReference.VALEUR)
    rc = ResultatCalcul(calcul_id="scn:calc:a", valeur="42", type="decimal")
    assert resoudre_reference(ref, sc, resultats_calculs={"scn:calc:a": rc}) == Decimal("42")


def test_resolution_cible_absente_leve():
    ref = ValeurReference(type="reference", cible="scn:actor:absent",
                          attribut=AttributReference.DISPLAY_NAME)
    with pytest.raises(ErreurResolution):
        resoudre_reference(ref, _scenario())


def test_resolution_attribut_invalide_leve():
    ref = ValeurReference(type="reference", cible="scn:actor:s",
                          attribut=AttributReference.DATE)
    with pytest.raises(ErreurResolution):
        resoudre_reference(ref, _scenario())


def test_resolution_calcul_inconnu_leve():
    ref = ValeurReference(type="reference", cible="scn:calc:absent",
                          attribut=AttributReference.VALEUR)
    with pytest.raises(ErreurResolution):
        resoudre_reference(ref, _scenario())
