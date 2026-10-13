"""Tests de la normalisation des numeros d'articles."""
from beaume.legal.normalisation import (
    egal_numero,
    format_humain,
    normaliser_numero,
)


def test_normaliser_L_avec_points():
    assert normaliser_numero("L. 1234-1") == "L1234-1"


def test_normaliser_L_avec_espace():
    assert normaliser_numero("L 1234-1") == "L1234-1"


def test_normaliser_L_compact():
    assert normaliser_numero("L1234-1") == "L1234-1"


def test_normaliser_R():
    assert normaliser_numero("R. 1234-1") == "R1234-1"


def test_normaliser_D():
    assert normaliser_numero("D. 1234-1") == "D1234-1"


def test_normaliser_numero_simple():
    assert normaliser_numero("1240") == "1240"


def test_normaliser_numero_simple_avec_espace():
    assert normaliser_numero(" 1240 ") == "1240"


def test_normaliser_annexe():
    assert normaliser_numero("Annexe 2") == "Annexe2"


def test_normaliser_vide():
    assert normaliser_numero("") == ""
    assert normaliser_numero(None) == ""


def test_format_humain_L():
    assert format_humain("L1234-1") == "L. 1234-1"


def test_format_humain_R():
    assert format_humain("R1234-1") == "R. 1234-1"


def test_format_humain_numero():
    assert format_humain("1240") == "1240"


def test_format_humain_vide():
    assert format_humain("") == ""


def test_egal_numero_formats_differents():
    assert egal_numero("L. 1234-1", "L1234-1") is True
    assert egal_numero("L 1234-1", "L. 1234-1") is True


def test_egal_numero_differents():
    assert egal_numero("L1234-1", "L1234-2") is False


def test_aller_retour():
    for original in ["L. 1234-1", "R. 1234-1", "D. 1234-1"]:
        normalise = normaliser_numero(original)
        reformate = format_humain(normalise)
        assert reformate == original
