"""Tests du profiler."""
import time
import pytest

from beaume.utils.profiler import (
    Profil,
    chronometre,
    profil_actif,
    profilage_par_env,
)


def test_chronometre_passe_la_valeur():
    @chronometre("test")
    def f(x):
        return x * 2
    assert f(21) == 42


def test_chronometre_preserve_nom():
    @chronometre("test")
    def ma_fonction():
        return 1
    assert ma_fonction.__name__ == "ma_fonction"


def test_sans_profil_aucune_mesure():
    """Sans profil actif, la fonction est appelee normalement."""
    appels = []

    @chronometre("etape")
    def f():
        appels.append(1)
        return 1

    f()
    assert appels == [1]


def test_avec_profil_mesure():
    @chronometre("etape")
    def f():
        time.sleep(0.01)
        return 1

    with profil_actif("test") as p:
        f()
        f()

    assert p.nombre("etape") == 2
    assert p.total("etape") >= 0.02


def test_profil_rapport_vide():
    p = Profil(nom="vide")
    assert "aucune mesure" in p.rapport()


def test_profil_rapport_avec_mesures():
    p = Profil(nom="test")
    p.enregistrer("a", 0.5)
    p.enregistrer("a", 0.3)
    p.enregistrer("b", 0.2)
    assert p.nombre("a") == 2
    assert abs(p.total("a") - 0.8) < 0.001
    assert abs(p.temps_total() - 1.0) < 0.001
    rapport = p.rapport()
    assert "a" in rapport
    assert "b" in rapport
    assert "TOTAL" in rapport


def test_profil_vider():
    p = Profil()
    p.enregistrer("a", 1.0)
    p.vider()
    assert p.temps_total() == 0.0


def test_imbrication():
    """Deux contextes imbriques enregistrent chacun dans leur profil."""
    @chronometre("etape")
    def f():
        return 1

    with profil_actif("externe") as outer:
        f()
        with profil_actif("interne") as inner:
            f()
        f()

    assert inner.nombre("etape") == 1
    assert outer.nombre("etape") == 3


def test_profilage_par_env(monkeypatch):
    monkeypatch.delenv("BEAUME_PROFILE", raising=False)
    assert profilage_par_env() is False
    monkeypatch.setenv("BEAUME_PROFILE", "1")
    assert profilage_par_env() is True
    monkeypatch.setenv("BEAUME_PROFILE", "0")
    assert profilage_par_env() is False


def test_chronometre_transmet_les_arguments():
    @chronometre("test")
    def addition(a, b):
        return a + b

    with profil_actif("test"):
        assert addition(2, 3) == 5
        assert addition(a=10, b=20) == 30