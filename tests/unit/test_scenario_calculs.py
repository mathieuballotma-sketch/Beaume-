"""Tests du registre ferme d'operations de calcul."""
from __future__ import annotations

import pytest

from beaume.scenario.calculs import (
    DependanceCirculaire,
    OperationInconnue,
    ReferenceAbsente,
    TypeIncompatible,
    resoudre,
)
from beaume.scenario.model import Calcul


def test_ajouter_jours():
    r = resoudre([Calcul(calcul_id="scn:calc:j", operation="ajouter_jours", arguments=["2020-01-01", "10"])])
    assert r["scn:calc:j"].valeur == "2020-01-11"
    assert r["scn:calc:j"].type == "date"


def test_soustraire_jours():
    r = resoudre([Calcul(calcul_id="scn:calc:j", operation="soustraire_jours", arguments=["2020-01-11", "10"])])
    assert r["scn:calc:j"].valeur == "2020-01-01"


def test_difference_jours():
    r = resoudre([Calcul(calcul_id="scn:calc:d", operation="difference_jours", arguments=["2020-03-01", "2020-02-01"])])
    assert r["scn:calc:d"].valeur == "29"
    assert r["scn:calc:d"].type == "int"


def test_multiplier_montant():
    r = resoudre([Calcul(calcul_id="scn:calc:m", operation="multiplier_montant", arguments=["100.50", "2"])])
    assert r["scn:calc:m"].valeur == "201.00"
    assert r["scn:calc:m"].type == "decimal"


def test_somme_montants():
    r = resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["100.00", "50.00"])])
    assert r["scn:calc:a"].valeur == "150.00"


def test_chaine_de_calculs():
    r = resoudre([
        Calcul(calcul_id="scn:calc:plus30", operation="ajouter_jours", arguments=["2020-01-01", "30"]),
        Calcul(calcul_id="scn:calc:double", operation="multiplier_montant", arguments=["100.00", "2"]),
    ])
    assert r["scn:calc:plus30"].valeur == "2020-01-31"
    assert r["scn:calc:double"].valeur == "200.00"


def test_reference_absente():
    with pytest.raises(ReferenceAbsente):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["scn:calc:absent", "1"])])


def test_reference_absente_litteral_invalide():
    with pytest.raises(ReferenceAbsente):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["abc", "1"])])


def test_dependance_circulaire():
    with pytest.raises(DependanceCirculaire):
        resoudre([
            Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["scn:calc:b", "1"]),
            Calcul(calcul_id="scn:calc:b", operation="somme_montants", arguments=["scn:calc:a", "1"]),
        ])


def test_dependance_soi_meme():
    with pytest.raises(DependanceCirculaire):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["scn:calc:a", "1"])])


def test_operation_inconnue():
    with pytest.raises(OperationInconnue):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="eval", arguments=["x"])])


def test_type_incompatible_date_vs_decimal():
    with pytest.raises(TypeIncompatible):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="ajouter_jours", arguments=["100.00", "10"])])


def test_type_incompatible_decimal_vs_date():
    with pytest.raises(TypeIncompatible):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["2020-01-01", "1"])])


def test_calcul_id_duplique():
    with pytest.raises(ReferenceAbsente):
        resoudre([
            Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["1", "1"]),
            Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["2", "2"]),
        ])


def test_prefixe_calcul_id():
    with pytest.raises(Exception):
        Calcul(calcul_id="calc-1", operation="somme_montants", arguments=["1", "1"])



def test_montant_100_accepte():
    r = resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["100", "1"])])
    assert r["scn:calc:a"].valeur == "101.00"


def test_montant_100_00_accepte():
    r = resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["100.00", "1.00"])])
    assert r["scn:calc:a"].valeur == "101.00"


def test_argument_count_insuffisant():
    with pytest.raises(TypeIncompatible, match="attend 2 arguments"):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="ajouter_jours", arguments=["2020-01-01"])])


def test_argument_count_excedentaire():
    with pytest.raises(TypeIncompatible, match="attend 2 arguments"):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="ajouter_jours", arguments=["2020-01-01", "1", "2"])])


def test_overflow_date():
    with pytest.raises(TypeIncompatible, match="depassement"):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="ajouter_jours", arguments=["9999-12-31", "1"])])


def test_nan_rejete():
    with pytest.raises(ReferenceAbsente, match="non-fini"):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["NaN", "1"])])


def test_infinity_rejete():
    with pytest.raises(ReferenceAbsente, match="non-fini"):
        resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["Infinity", "1"])])



# --- F-a2-beta1 : inputs non finis rejetes ---

def test_inputs_nan_rejete():
    from decimal import Decimal
    with pytest.raises(TypeIncompatible, match="non-fini"):
        resoudre(
            [Calcul(calcul_id="scn:calc:a", operation="somme_montants",
                    arguments=["x", "1"])],
            inputs={"x": Decimal("NaN")},
        )


def test_inputs_infini_rejete():
    from decimal import Decimal
    with pytest.raises(TypeIncompatible, match="non-fini"):
        resoudre(
            [Calcul(calcul_id="scn:calc:a", operation="somme_montants",
                    arguments=["x", "1"])],
            inputs={"x": Decimal("Infinity")},
        )



# --- F-b2-gamma : roles fermes ---

def test_role_inconnu_leve_value_error():
    """Acces direct a l'enum : ValueError standard Python.
    Via Pydantic (cf. test_acteur_role_ferme_via_scenario),
    la meme erreur remonte en ValidationError."""
    import pytest
    from beaume.scenario.model import RoleActeur
    with pytest.raises(ValueError):
        RoleActeur("super_administrateur")


def test_role_demandeur_accepte():
    from beaume.scenario.model import RoleActeur
    assert RoleActeur("demandeur") is RoleActeur.DEMANDEUR


def test_acteur_role_ferme_via_scenario():
    import pytest
    from pydantic import ValidationError
    from beaume.scenario.model import Scenario
    with pytest.raises(ValidationError):
        Scenario(
            schema_version="0.3",
            scenario_id="BEAUME-SC-0002",
            scenario_version=1,
            partition="dev",
            domain="d", language="fr", created_at="2026-10-23",
            sources=[],
            actors=[{
                "actor_id": "scn:actor:x", "display_name": "X",
                "roles": ["inventeur"],
                "provenance": {"mode": "cree", "regle": "r", "parametres": {}},
            }],
            events=[{
                "event_id": "scn:event:e",
                "date": {"valeur": "2020-01-01", "precision": "jour"},
                "description": "d", "actors_impliques": ["scn:actor:x"],
                "provenance": {"mode": "cree", "regle": "r", "parametres": {}},
            }],
            documents=[{
                "document_id": "scn:doc:d", "titre": "t",
                "date": {"valeur": "2026-01-01", "precision": "jour"},
                "nature": "x", "auteur": "scn:actor:x",
                "assertions": [],
                "contenu": {"mode": "texte", "texte": "x"},
                "provenance": {"mode": "cree", "regle": "r", "parametres": {}},
            }],
            propositions_juridiques=[],
        )


# --- F-b2-gamma : arrondi HALF_UP 2 decimales ---

def test_arrondi_multiplier_3_decimales():
    from beaume.scenario.calculs import resoudre
    from beaume.scenario.model import Calcul
    r = resoudre([Calcul(
        calcul_id="scn:calc:a", operation="multiplier_montant",
        arguments=["1000.00", "0.333"],
    )])
    assert r["scn:calc:a"].valeur == "333.00"


def test_arrondi_multiplier_2_decimales_inchange():
    from beaume.scenario.calculs import resoudre
    from beaume.scenario.model import Calcul
    r = resoudre([Calcul(
        calcul_id="scn:calc:a", operation="multiplier_montant",
        arguments=["100.50", "2"],
    )])
    assert r["scn:calc:a"].valeur == "201.00"


def test_arrondi_somme_2_decimales():
    from beaume.scenario.calculs import resoudre
    from beaume.scenario.model import Calcul
    r = resoudre([Calcul(
        calcul_id="scn:calc:a", operation="somme_montants",
        arguments=["100.00", "50.00"],
    )])
    assert r["scn:calc:a"].valeur == "150.00"


def test_arrondi_half_up_au_dessus():
    from beaume.scenario.calculs import resoudre
    from beaume.scenario.model import Calcul
    # 0.005 -> HALF_UP -> 0.01
    r = resoudre([Calcul(
        calcul_id="scn:calc:a", operation="multiplier_montant",
        arguments=["100.00", "0.00005"],
    )])
    assert r["scn:calc:a"].valeur == "0.01"


def test_arrondi_half_up_au_dessous():
    from beaume.scenario.calculs import resoudre
    from beaume.scenario.model import Calcul
    # 0.004 -> HALF_UP -> 0.00
    r = resoudre([Calcul(
        calcul_id="scn:calc:a", operation="multiplier_montant",
        arguments=["100.00", "0.00004"],
    )])
    assert r["scn:calc:a"].valeur == "0.00"


def test_arrondi_chaine():
    from beaume.scenario.calculs import resoudre
    from beaume.scenario.model import Calcul
    # 1000.00 * 0.333 = 333.00000, quantize -> 333.00
    # puis 333.00 + 0.01 = 333.01
    r = resoudre([
        Calcul(calcul_id="scn:calc:a", operation="multiplier_montant",
               arguments=["1000.00", "0.333"]),
        Calcul(calcul_id="scn:calc:b", operation="somme_montants",
               arguments=["scn:calc:a", "0.01"]),
    ])
    assert r["scn:calc:a"].valeur == "333.00"
    assert r["scn:calc:b"].valeur == "333.01"


# --- H04 : difference negative autorisee ---

def test_difference_negative_autorisee():
    from beaume.scenario.calculs import resoudre
    from beaume.scenario.model import Calcul
    r = resoudre([Calcul(
        calcul_id="scn:calc:a", operation="difference_jours",
        arguments=["2020-01-01", "2021-01-01"],
    )])
    assert r["scn:calc:a"].valeur == "-366"
    assert r["scn:calc:a"].type == "int"
