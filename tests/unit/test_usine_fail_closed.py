"""Tests du préflight fail-closed de l'usine à dossiers.

Vérifie que tant que les templates hérités contiennent des constantes
d'affaire, la génération refuse de s'exécuter et n'écrit aucun dossier.
"""
from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pytest


@lru_cache(maxsize=1)
def _module():
    """Charge scripts/11_usine_a_dossiers.py sans import Python classique
    (le nom commence par un chiffre)."""
    import importlib.util

    chemin = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "11_usine_a_dossiers.py"
    )
    assert chemin.exists(), f"introuvable : {chemin}"
    spec = importlib.util.spec_from_file_location("usine_a_dossiers_test", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_refuse_si_constantes_presentes():
    mod = _module()
    with pytest.raises(SystemExit) as excinfo:
        mod.preflight()
    msg = str(excinfo.value)
    assert "non paramétré par scénario" in msg
    assert "vieil armand" in msg
    assert "sci jml" in msg


def test_preflight_detecte_les_cinq_constantes():
    """Non-régression sur un écart de diagnostic observé :
    la constante « article 2224 » ne matchait pas « 2224 du Code civil »,
    le préflight n'affichait que 4 constantes sur 5."""
    mod = _module()
    presentes, absentes = mod._detecter_constantes(mod._TEMPLATES_HERITES)
    assert len(presentes) == 5, f"attendu 5 constantes détectées, vu {presentes!r}"
    assert absentes == [], f"constantes non trouvées : {absentes!r}"


def test_preflight_ne_touche_a_aucun_dossier(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "DOSSIER_SORTIE", tmp_path)
    with pytest.raises(SystemExit):
        mod.main()
    assert list(tmp_path.iterdir()) == []


def test_generer_dossier_refuse_de_fonctionner():
    mod = _module()
    with pytest.raises(RuntimeError, match="templates non paramétrés"):
        mod.generer_dossier({"date_pret": "x"}, "dossier_x")


def test_marquer_inelegibles_ecrit_manifeste_sans_supprimer(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "DOSSIER_SORTIE", tmp_path)
    (tmp_path / "dossier_aaaa").mkdir()
    (tmp_path / "dossier_bbbb").mkdir()
    chemin = mod.marquer_inelegibles()
    assert chemin.exists()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["motif"] == "contamination_affaire"
    assert {d["nom"] for d in data["dossiers"]} == {"dossier_aaaa", "dossier_bbbb"}
    assert all(d["eligible_entrainement"] is False for d in data["dossiers"])
    assert (tmp_path / "dossier_aaaa").exists()
    assert (tmp_path / "dossier_bbbb").exists()


def test_montant_decimal_preserve_les_centimes():
    """123 456,41 euros ne doit pas devenir 41 euros."""
    mod = _module()
    montants = mod.extraire_montants(
        "un prêt de 123 456,41 euros et un autre de 41 euros"
    )
    valeurs = [m["valeur"] for m in montants]
    assert Decimal("123456.41") in valeurs
    assert Decimal("41.00") in valeurs
    assert valeurs[0] == Decimal("123456.41")


def test_montant_ordre_stable():
    mod = _module()
    texte = "1000 euros, 2000 euros, 3000 euros"
    a = [m["valeur"] for m in mod.extraire_montants(texte)]
    b = [m["valeur"] for m in mod.extraire_montants(texte)]
    assert a == b
    assert a == [Decimal("1000.00"), Decimal("2000.00"), Decimal("3000.00")]


def test_dates_contraintes_identifiants():
    mod = _module()
    mentions = {
        "date_0": {"id": "date_0", "valeur": "1 janvier 2020"},
        "date_1": {"id": "date_1", "valeur": "1 juin 2020"},
        "date_2": {"id": "date_2", "valeur": "1 décembre 2020"},
    }
    assert mod.verifier_chronologie(
        {"date_pret": "date_0", "date_dech": "date_1", "date_assign": "date_2"},
        mentions,
    ) is True
    assert mod.verifier_chronologie(
        {"date_pret": "date_99", "date_dech": "date_1", "date_assign": "date_2"},
        mentions,
    ) is False
    assert mod.verifier_chronologie(
        {"date_pret": "date_2", "date_dech": "date_1", "date_assign": "date_0"},
        mentions,
    ) is False