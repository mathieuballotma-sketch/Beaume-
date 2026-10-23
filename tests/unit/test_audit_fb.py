"""Tests adverses F-b1 / F-b2 (audit Grok Bot, 23/10/2026).

test_D* : comportement attendu, rouge sur le code livre si defaut.
test_H* : comportement actuel documente, decision a confirmer.
test_R* : non-regression des garanties revendiquees.
Les tests travaillent sur une racine temporaire (tmp_path) : aucun
fichier du depot n'est modifie.
"""
from __future__ import annotations

import copy
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from beaume.scenario import RapportValidation, ResultatControle, Scenario, valider_scenario
from beaume.scenario.calculs import resoudre
from beaume.scenario.model import Calcul
from beaume.scenario.validateur import VERSION_REGLE

RACINE = Path(__file__).resolve().parents[2]
EXEMPLE = RACINE / "data/scenarios/exemples/beaume-sc-licenciement-0002-v1.json"


@pytest.fixture
def racine(tmp_path):
    dst = tmp_path / "data/scenarios/structures"
    shutil.copytree(RACINE / "data/scenarios/structures", dst)
    return tmp_path


def _ex():
    return json.loads(EXEMPLE.read_text(encoding="utf-8"))


def _ctl(r, cid):
    return next(c for c in r.controles if c.controle_id == cid)


# ---------- R : garanties revendiquees ----------

def test_R01_exemple_accepte_avec_racine(racine):
    sc = Scenario(**_ex())
    r = valider_scenario(sc, racine=racine)
    assert r.accepte(sc, racine=racine) is True
    assert len(r.controles) == 12


def test_R02_template_modifie_apres_rapport_refuse(racine):
    sc = Scenario(**_ex())
    r = valider_scenario(sc, racine=racine)
    f = racine / "data/scenarios/structures/saisine_prud_hommes.md"
    f.write_text(f.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert r.accepte(sc, racine=racine) is False


def test_R03_sans_racine_refuse(racine):
    sc = Scenario(**_ex())
    r = valider_scenario(sc, racine=racine)
    assert r.accepte(sc) is False
    r2 = valider_scenario(sc)
    assert _ctl(r2, "generation.templates_coherents").resultat is ResultatControle.INDETERMINE


def test_R04_chemin_template_hors_structures(racine):
    d = _ex()
    d["documents"][0]["contenu"]["chemin"] = "../../etc/hosts"
    sc = Scenario(**d)
    r = valider_scenario(sc, racine=racine)
    assert _ctl(r, "generation.templates_coherents").resultat is ResultatControle.ECHOUE
    assert r.accepte(sc, racine=racine) is False


def test_R05_inversion_nom_demandeur_refusee(racine):
    d = _ex()
    d["documents"][0]["contenu"]["champs"]["NOM_DEMANDEUR"]["cible"] = "scn:actor:employeur"
    sc = Scenario(**d)
    r = valider_scenario(sc, racine=racine)
    assert _ctl(r, "structure.balises_roles").resultat is ResultatControle.ECHOUE


def test_R06_rapport_v3_refuse(racine):
    sc = Scenario(**_ex())
    r = valider_scenario(sc, racine=racine)
    for c in r.controles:
        c.version_regle = "3"
    assert r.accepte(sc, racine=racine) is False


def test_R07_role_inconnu_refuse_au_parsing():
    d = _ex()
    d["actors"][0]["roles"].append("Demandeur")
    with pytest.raises(ValidationError):
        Scenario(**d)


def test_R08_chronologie_inversee_refusee(racine):
    d = _ex()
    d["events"].reverse()
    r = valider_scenario(Scenario(**d), racine=racine)
    assert _ctl(r, "scenario.evenements_chronologiques").resultat is ResultatControle.ECHOUE


def test_R09_dates_egales_acceptees(racine):
    d = _ex()
    d["events"][1]["date"] = d["events"][0]["date"]
    r = valider_scenario(Scenario(**d), racine=racine)
    assert _ctl(r, "scenario.evenements_chronologiques").resultat is ResultatControle.REUSSI


def test_R10_date_evenement_manquante_refusee():
    d = _ex()
    del d["events"][0]["date"]
    with pytest.raises(ValidationError):
        Scenario(**d)


@pytest.mark.parametrize("op,a,b,attendu", [
    ("multiplier_montant", "10.005", "1", "10.01"),
    ("multiplier_montant", "1000.00", "0.333", "333.00"),
    ("somme_montants", "0.005", "0.000", "0.01"),
    ("somme_montants", "2.675", "0", "2.68"),
])
def test_R11_arrondi_half_up(op, a, b, attendu):
    r = resoudre([Calcul(calcul_id="scn:calc:a", operation=op, arguments=[a, b])])
    assert r["scn:calc:a"].valeur == attendu


def test_R12_quantize_enorme_fail_closed():
    with pytest.raises(Exception) as ei:
        resoudre([Calcul(calcul_id="scn:calc:a", operation="somme_montants",
                         arguments=["9" * 30, "1"])])
    assert type(ei.value).__name__ == "TypeIncompatible"


def test_R13_difference_negative_autorisee_H04():
    r = resoudre([Calcul(calcul_id="scn:calc:a", operation="difference_jours",
                         arguments=["2020-01-01", "2021-01-01"])])
    assert r["scn:calc:a"].valeur == "-366"


def test_R14_proposition_vers_acteur_refusee_H06(racine):
    d = _ex()
    d["propositions_juridiques"][0]["references_invoquees"] = ["scn:actor:salarie"]
    r = valider_scenario(Scenario(**d), racine=racine)
    assert _ctl(r, "structure.references_resolues").resultat is ResultatControle.ECHOUE


# ---------- D : defauts ----------

def test_D01_rapport_doit_couvrir_tous_les_templates(racine):
    """Retirer une empreinte du rapport ne doit pas le rendre acceptable."""
    sc = Scenario(**_ex())
    brut = valider_scenario(sc, racine=racine).model_dump(mode="json")
    cle = sorted(brut["empreintes_templates"])[0]
    del brut["empreintes_templates"][cle]
    assert RapportValidation(**brut).accepte(sc, racine=racine) is False


def test_D02_empreinte_etrangere_refusee(racine):
    """Une empreinte pour un template non utilise par le scenario est suspecte."""
    sc = Scenario(**_ex())
    brut = valider_scenario(sc, racine=racine).model_dump(mode="json")
    autre = "data/scenarios/structures/contrat_pret.md"
    import hashlib
    brut["empreintes_templates"][autre] = hashlib.sha256((racine / autre).read_bytes()).hexdigest()
    assert RapportValidation(**brut).accepte(sc, racine=racine) is False


def test_D03_nom_suffixe_sans_role_dans_enum(racine):
    """contrat_pret.md utilise [NOM_EMPRUNTEUR] mais 'emprunteur' n'existe pas
    dans RoleActeur : le template est inutilisable. Toute balise NOM_<x> d'un
    template doit correspondre a un role du contrat."""
    from beaume.scenario.model import RoleActeur
    roles = {r.value for r in RoleActeur}
    import re
    manquants = []
    for f in sorted((RACINE / "data/scenarios/structures").glob("*.md")):
        for b in set(re.findall(r"\[NOM_([A-Z0-9_]+)\]", f.read_text(encoding="utf-8"))):
            if b.lower() not in roles:
                manquants.append(f"{f.name}:{b}")
    assert manquants == []


def test_D04_inversion_avocats_detectee(racine):
    d = _ex()
    d["actors"].append({"actor_id": "scn:actor:av_s", "display_name": "Me A",
                        "roles": ["avocat_demandeur"], "provenance": {"mode": "cree", "regle": "r", "parametres": {}}})
    d["actors"].append({"actor_id": "scn:actor:av_e", "display_name": "Me B",
                        "roles": ["avocat_defendeur"], "provenance": {"mode": "cree", "regle": "r", "parametres": {}}})
    ch = d["documents"][1]["contenu"]["champs"]
    ch["AVOCAT_DEMANDEUR"] = {"type": "reference", "cible": "scn:actor:av_e", "attribut": "display_name"}
    ch["AVOCAT_DEFENDEUR"] = {"type": "reference", "cible": "scn:actor:av_s", "attribut": "display_name"}
    sc = Scenario(**d)
    r = valider_scenario(sc, racine=racine)
    assert r.accepte(sc, racine=racine) is False


# ---------- H : decisions a confirmer ----------

def test_H01_nom_absent_refuse(racine):
    d = _ex()
    d["documents"][0]["contenu"]["champs"]["NOM_DEFENDEUR"] = {"type": "absent", "motif": "non_pertinent"}
    r = valider_scenario(Scenario(**d), racine=racine)
    assert _ctl(r, "structure.balises_roles").resultat is ResultatControle.ECHOUE


def test_H02_nom_litteral_refuse(racine):
    d = _ex()
    d["documents"][0]["contenu"]["champs"]["NOM_DEFENDEUR"] = {"type": "litteral", "valeur": "SARL X"}
    r = valider_scenario(Scenario(**d), racine=racine)
    assert _ctl(r, "structure.balises_roles").resultat is ResultatControle.ECHOUE


def test_H03_chronologie_depend_de_l_ordre_de_la_liste(racine):
    """Meme faits, ordre JSON different -> verdict different (ordre declaratif)."""
    d = _ex()
    d["events"].reverse()
    r = valider_scenario(Scenario(**d), racine=racine)
    assert _ctl(r, "scenario.evenements_chronologiques").resultat is ResultatControle.ECHOUE


def test_H04_precision_mois_comparee_au_jour(racine):
    """2019-03 (precision mois, stocke 2019-03-01) avant 2019-03-01 jour : accepte."""
    d = _ex()
    d["events"][0]["date"] = {"valeur": "2019-03-15", "precision": "mois"}
    d["events"][1]["date"] = {"valeur": "2019-03-02", "precision": "jour"}
    r = valider_scenario(Scenario(**d), racine=racine)
    # comportement actuel : ECHOUE alors que l'ordre est indecidable au mois pres
    assert _ctl(r, "scenario.evenements_chronologiques").resultat is ResultatControle.ECHOUE


def test_H05_document_anterieur_aux_evenements_non_controle(racine):
    d = _ex()
    d["documents"][0]["date"] = "2010-01-01"  # saisine avant l'embauche
    sc = Scenario(**d)
    r = valider_scenario(sc, racine=racine)
    assert r.accepte(sc, racine=racine) is True


def test_H06_un_seul_evenement_reussi_et_non_na(racine):
    d = _ex()
    d["events"] = d["events"][:1]
    r = valider_scenario(Scenario(**d), racine=racine)
    assert _ctl(r, "scenario.evenements_chronologiques").resultat is ResultatControle.REUSSI


def test_H07_double_arrondi_en_chaine():
    r = resoudre([
        Calcul(calcul_id="scn:calc:a", operation="multiplier_montant", arguments=["0.005", "1"]),
        Calcul(calcul_id="scn:calc:b", operation="multiplier_montant", arguments=["scn:calc:a", "3"]),
    ])
    assert r["scn:calc:b"].valeur == "0.03"  # 0.015 exact -> 0.02 sans arrondi intermediaire
