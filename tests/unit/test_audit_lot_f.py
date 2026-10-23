"""Tests adverses de l'audit lot F (Grok Bot, 2026-10-23).

Convention :
- tests `test_D*` : comportement ATTENDU ; ils echouent sur le code
  d'origine (defaut confirme) et passent apres correctifs.patch ;
- tests `test_H*` : documentent le comportement ACTUEL sur un point
  que le contrat ne tranche pas (hypothese a trancher par Mathieu) ;
- tests `test_R*` : non-regression des garanties revendiquees.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from beaume.scenario import (
    Controle,
    Montant,
    RapportValidation,
    ResultatControle,
    Scenario,
    valider_scenario,
)
from beaume.scenario.calculs import resoudre, TypeIncompatible, DependanceCirculaire
from beaume.scenario.model import Calcul
from beaume.scenario.validateur import VERSION_REGLE

RACINE = Path(__file__).resolve().parents[2]
EXEMPLE = RACINE / "data" / "scenarios" / "exemples" / "beaume-sc-licenciement-0002-v1.json"


def _prov():
    return {"mode": "cree", "regle": "r", "parametres": {}}


def _base():
    return {
        "schema_version": "0.3", "scenario_id": "BEAUME-SC-9999-v1",
        "scenario_version": 1, "partition": "dev", "domain": "d",
        "language": "fr", "created_at": "2026-10-23", "sources": [],
        "actors": [
            {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"], "provenance": _prov()},
            {"actor_id": "scn:actor:e", "display_name": "E", "roles": ["defendeur"], "provenance": _prov()},
        ],
        "events": [{"event_id": "scn:event:x", "date": "2020-01-01", "description": "d",
                    "actors_impliques": ["scn:actor:s"], "provenance": _prov()}],
        "documents": [{"document_id": "scn:doc:d", "titre": "t", "date": "2026-01-01",
                       "nature": "saisine", "auteur": "scn:actor:s", "assertions": [],
                       "contenu": {"mode": "texte", "texte": "x"}, "provenance": _prov()}],
        "calculs": [], "propositions_juridiques": [],
    }


def _avec_champ(nom, valeur, decl):
    d = _base()
    d["documents"][0]["contenu"]["champs"] = {nom: valeur}
    d["documents"][0]["contenu"]["declarations"] = {nom: decl}
    return d


def _ctl(rapport, cid):
    return next(c for c in rapport.controles if c.controle_id == cid)


def _valeurs(d):
    return _ctl(valider_scenario(Scenario(**d)), "structure.valeurs_champs").resultat


# ---------- Defauts confirmes (echouent avant correctif) ----------

@pytest.mark.parametrize("brut", ["-500", "1_000", " 12 ", "1e999999", "25000,00", "1.234", "+5", "9" * 40])
def test_D01_montant_litteral_format_strict(brut):
    d = _avec_champ("M", {"type": "litteral", "valeur": brut}, "montant")
    assert _valeurs(d) is ResultatControle.ECHOUE


@pytest.mark.parametrize("brut", ["1_000", " 7", "\u0663", "+3"])
def test_D02_entier_litteral_format_strict(brut):
    d = _avec_champ("N", {"type": "litteral", "valeur": brut}, "entier")
    assert _valeurs(d) is ResultatControle.ECHOUE


@pytest.mark.parametrize("brut", ["20260101", "2026-W01-1", "2026-01-01T00:00"])
def test_D03_date_litterale_format_aaaa_mm_jj(brut):
    d = _avec_champ("D", {"type": "litteral", "valeur": brut}, "date")
    assert _valeurs(d) is ResultatControle.ECHOUE


def test_D04_absent_motif_autre_exige_precision():
    d = _avec_champ("L", {"type": "absent", "motif": "autre"}, "texte")
    with pytest.raises(ValidationError):
        Scenario(**d)
    d = _avec_champ("L", {"type": "absent", "motif": "autre", "precision": "lieu tenu secret"}, "texte")
    assert _valeurs(d) is ResultatControle.REUSSI


def test_D05_accepte_ne_peut_pas_affaiblir_les_controles_requis():
    d = _avec_champ("M", {"type": "litteral", "valeur": "banane"}, "montant")
    sc = Scenario(**d)
    r = valider_scenario(sc)
    assert r.accepte(sc) is False
    assert r.accepte(sc, obligatoires=set()) is False


def test_D06_rapport_extra_forbid():
    with pytest.raises(ValidationError):
        Controle(controle_id="x", version_regle="1", categorie="structure",
                 objets_controles=[], resultat="reussi", intrus=1)
    sc = Scenario(**_base())
    brut = valider_scenario(sc).model_dump(mode="json")
    brut["accepte_force"] = True
    with pytest.raises(ValidationError):
        RapportValidation(**brut)


def test_D07_dates_valides_n_est_plus_tautologique():
    d = _base()
    d["events"][0]["date"] = "2030-01-01"  # posterieure a created_at
    r = valider_scenario(Scenario(**d))
    assert _ctl(r, "structure.dates_valides").resultat is ResultatControle.ECHOUE


def test_D08_auteur_egal_destinataire_refuse():
    d = _base()
    d["documents"][0]["destinataire"] = "scn:actor:s"
    r = valider_scenario(Scenario(**d))
    assert _ctl(r, "scenario.acteurs_roles_coherents").resultat is ResultatControle.ECHOUE


@pytest.mark.parametrize("brut", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_R12_montant_modele_non_fini_validationerror(brut):
    with pytest.raises(ValidationError):
        Montant(valeur=brut)


def test_D10_version_regle_incrementee():
    # Les regles ont change entre F-a1 et F-a2-beta2 : un rapport "1" est perime.
    assert VERSION_REGLE != "1"


def test_D11_template_conclusions_pour_demandeur():
    lignes = (RACINE / "data/scenarios/structures/conclusions_prud.md").read_text(encoding="utf-8").splitlines()
    i = lignes.index("**POUR :**")
    assert lignes[i + 1].strip() == "[NOM_DEMANDEUR]"


def test_D12_verifier_templates_existence_parite_chemin():
    from beaume.scenario.validateur import verifier_templates
    d = json.loads(EXEMPLE.read_text(encoding="utf-8"))
    assert verifier_templates(Scenario(**d), RACINE).resultat is ResultatControle.REUSSI
    d2 = copy.deepcopy(d)
    d2["documents"][0]["contenu"]["chemin"] = "data/scenarios/structures/inexistant.md"
    assert verifier_templates(Scenario(**d2), RACINE).resultat is ResultatControle.ECHOUE
    d3 = copy.deepcopy(d)
    del d3["documents"][0]["contenu"]["champs"]["LIEU"]
    del d3["documents"][0]["contenu"]["declarations"]["LIEU"]
    assert verifier_templates(Scenario(**d3), RACINE).resultat is ResultatControle.ECHOUE
    d4 = copy.deepcopy(d)
    d4["documents"][0]["contenu"]["chemin"] = "../../../etc/hosts"
    assert verifier_templates(Scenario(**d4), RACINE).resultat is ResultatControle.ECHOUE


def test_D13_cli_importe_le_paquet_de_son_propre_arbre(tmp_path):
    """Sans effet de bord : on charge le script sans executer main()."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    code = ("import runpy,sys; g=runpy.run_path(sys.argv[1], run_name='audit'); "
            "print(g['RAPPORTS'])")
    p = subprocess.run([sys.executable, "-c", code, str(RACINE / "scripts/valider_scenario.py")],
                       cwd=tmp_path, env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip().startswith(str(RACINE)), p.stdout


def test_D14_cli_scenario_invalide_sans_traceback(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({"schema_version": "0.3"}), encoding="utf-8")
    p = subprocess.run([sys.executable, str(RACINE / "scripts/valider_scenario.py"), str(f)],
                       capture_output=True, text=True)
    assert p.returncode == 3, p.stderr
    assert "Traceback" not in p.stderr


# ---------- Hypotheses a trancher (comportement actuel documente) ----------

@pytest.mark.parametrize("brut", ["", "   ", "\n\t"])
def test_D15_litteral_vide_ou_blanc_refuse(brut):
    # Decision H01 tranchee par Mathieu le 23/10/2026 : refus.
    d = _avec_champ("T", {"type": "litteral", "valeur": brut}, "texte")
    with pytest.raises(ValidationError):
        Scenario(**d)


def test_H02_absent_accepte_sur_tout_champ_aucune_notion_d_obligatoire():
    d = _avec_champ("NOM_DEFENDEUR", {"type": "absent", "motif": "non_pertinent"}, "texte")
    assert Scenario(**d) and _valeurs(d) is ResultatControle.REUSSI


def test_H03_inversion_des_parties_structurellement_valide():
    d = _avec_champ("NOM_DEMANDEUR", {"type": "reference", "cible": "scn:actor:e", "attribut": "display_name"}, "texte")
    r = valider_scenario(Scenario(**d))
    sc = Scenario(**d)
    assert r.accepte(sc) is True  # personne ne relie la balise au role


def test_H04_difference_jours_negative_acceptee():
    r = resoudre([Calcul(calcul_id="scn:calc:a", operation="difference_jours",
                         arguments=["2020-01-01", "2021-01-01"])])
    assert r["scn:calc:a"].valeur == "-366"


def test_H05_montant_calcule_negatif_ou_sans_arrondi():
    r = resoudre([Calcul(calcul_id="scn:calc:a", operation="multiplier_montant",
                         arguments=["1000.00", "0.333"])])
    assert r["scn:calc:a"].valeur == "333.00000"  # aucune regle d'arrondi au centime


def test_H06_references_invoquees_vers_acteur_refusees():
    d = _base()
    d["propositions_juridiques"] = [{"proposition_id": "scn:prop:p", "type": "moyen", "contenu": "c",
                                     "references_invoquees": ["scn:actor:s"], "provenance": _prov()}]
    r = valider_scenario(Scenario(**d))
    assert _ctl(r, "structure.references_resolues").resultat is ResultatControle.ECHOUE


# ---------- Non-regression des garanties revendiquees ----------

def test_R01_reference_inexistante():
    d = _avec_champ("N", {"type": "reference", "cible": "scn:actor:fantome", "attribut": "display_name"}, "texte")
    assert _valeurs(d) is ResultatControle.ECHOUE


def test_R02_mauvais_attribut_pour_la_cible():
    d = _avec_champ("N", {"type": "reference", "cible": "scn:actor:s", "attribut": "date"}, "date")
    r = valider_scenario(Scenario(**d))
    assert _ctl(r, "structure.references_resolues").resultat is ResultatControle.ECHOUE


def test_R03_reference_texte_dans_champ_date():
    d = _avec_champ("D", {"type": "reference", "cible": "scn:actor:s", "attribut": "display_name"}, "date")
    assert _valeurs(d) is ResultatControle.ECHOUE


def test_R04_cible_sans_prefixe_connu():
    d = _avec_champ("N", {"type": "reference", "cible": "s", "attribut": "display_name"}, "texte")
    r = valider_scenario(Scenario(**d))
    assert _ctl(r, "structure.references_resolues").resultat is ResultatControle.ECHOUE


def test_R05_prefixes_rendent_les_categories_disjointes():
    d = _base()
    d["actors"][0]["actor_id"] = "scn:event:x"
    with pytest.raises(ValidationError):
        Scenario(**d)


@pytest.mark.parametrize("ou", ["scenario", "doc", "contenu", "champ"])
def test_R06_champs_supplementaires_refuses(ou):
    d = _avec_champ("T", {"type": "litteral", "valeur": "a"}, "texte")
    cible = {"scenario": d, "doc": d["documents"][0], "contenu": d["documents"][0]["contenu"],
             "champ": d["documents"][0]["contenu"]["champs"]["T"]}[ou]
    cible["intrus"] = 1
    with pytest.raises(ValidationError):
        Scenario(**d)


def test_R07_empreinte_perimee():
    sc = Scenario(**_base())
    r = valider_scenario(sc)
    d = _base(); d["domain"] = "autre"
    assert r.accepte(Scenario(**d)) is False


def test_R08_cycle_long():
    with pytest.raises(DependanceCirculaire):
        resoudre([Calcul(calcul_id=f"scn:calc:{i}", operation="somme_montants",
                         arguments=[f"scn:calc:{(i + 1) % 3}", "1"]) for i in range(3)])


@pytest.mark.parametrize("args,op", [
    (["2020-01-01", "99999999999"], "ajouter_jours"),
    (["1e999999", "1e999999"], "multiplier_montant"),
    (["9" * 5000, "1"], "ajouter_jours"),
    (["NaN", "1"], "somme_montants"),
    (["Infinity", "1"], "somme_montants"),
])
def test_R09_nombres_extremes_fail_closed(args, op):
    with pytest.raises(Exception) as ei:
        resoudre([Calcul(calcul_id="scn:calc:a", operation=op, arguments=args)])
    assert not isinstance(ei.value, (OverflowError, ValueError)) or isinstance(ei.value, TypeIncompatible)


def test_R10_input_nan_filtre():
    with pytest.raises(TypeIncompatible):
        resoudre([], inputs={"x": Decimal("NaN")})


def test_R11_exemple_accepte():
    sc = Scenario(**json.loads(EXEMPLE.read_text(encoding="utf-8")))
    assert valider_scenario(sc).accepte(sc) is True
