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
    assert r["scn:calc:a"].valeur == "101"


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
