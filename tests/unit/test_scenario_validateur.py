"""Tests du validateur structurel et du rapport separe."""
from __future__ import annotations

import pytest

from beaume.scenario import (
    CONTROLES_OBLIGATOIRES,
    Controle,
    RapportValidation,
    ResultatControle,
    Scenario,
    valider_scenario,
)
from beaume.scenario.validateur import empreinte_scenario


def _prov():
    return {"mode": "cree", "regle": "r", "parametres": {}}


def _scenario(actors=None, events=None, documents=None, props=None, calculs=None):
    return Scenario(
        schema_version="0.3",
        scenario_id="BEAUME-SC-0002-v1",
        scenario_version=1,
        partition="dev",
        domain="d",
        language="fr",
        created_at="2026-10-23",
        sources=[],
        actors=actors or [
            {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"], "provenance": _prov()},
            {"actor_id": "scn:actor:e", "display_name": "E", "roles": ["defendeur"], "provenance": _prov()},
        ],
        events=events or [
            {"event_id": "scn:event:x",
             "date": {"valeur": "2020-01-01", "precision": "jour"},
             "description": "d",
             "actors_impliques": ["scn:actor:s"],
             "provenance": _prov()}
        ],
        documents=documents or [
            {"document_id": "scn:doc:saisine",
             "titre": "t",
             "date": {"valeur": "2026-01-01", "precision": "jour"},
             "nature": "saisine",
             "auteur": "scn:actor:s",
             "assertions": [],
             "contenu": {"mode": "texte", "texte": "x"},
             "provenance": _prov()}
        ],
        propositions_juridiques=props or [],
        calculs=calculs or [],
    )


def test_exemple_conforme_tous_controles_reussis():
    sc = _scenario()
    r = valider_scenario(sc)
    assert r.accepte(sc) is True
    assert {c.controle_id for c in r.controles} >= CONTROLES_OBLIGATOIRES


def test_reference_inexistante_echoue():
    sc = _scenario(events=[{
        "event_id": "scn:event:x",
        "date": {"valeur": "2020-01-01", "precision": "jour"},
        "description": "d",
        "actors_impliques": ["scn:actor:absent"],
        "provenance": _prov(),
    }])
    r = valider_scenario(sc)
    assert r.accepte(sc) is False
    echoue = [c for c in r.controles if c.controle_id == "structure.references_resolues"]
    assert echoue and echoue[0].resultat is ResultatControle.ECHOUE


def test_identifiant_duplique_echoue():
    sc = _scenario(actors=[
        {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"], "provenance": _prov()},
        {"actor_id": "scn:actor:s", "display_name": "S2", "roles": ["defendeur"], "provenance": _prov()},
    ])
    r = valider_scenario(sc)
    assert r.accepte(sc) is False
    c = [c for c in r.controles if c.controle_id == "structure.ids_uniques"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_controles_obligatoires_manquants():
    sc = _scenario()
    r = RapportValidation(
        rapport_id="r", scenario_id="s", scenario_version=1,
        schema_version="0.3", empreinte_scenario=empreinte_scenario(sc),
        genere_le="2026-10-23T00:00:00Z", controles=[],
    )
    assert r.accepte(sc) is False


def test_resultat_indetermine_refuse_acceptation():
    sc = _scenario()
    r = valider_scenario(sc)
    r.controles = [
        Controle(controle_id=cid, version_regle="1", categorie="structure",
                 objets_controles=[], resultat=ResultatControle.INDETERMINE, motif="x")
        for cid in CONTROLES_OBLIGATOIRES
    ]
    assert r.accepte(sc) is False


def test_non_applicable_sans_motif_refuse():
    sc = _scenario()
    r = valider_scenario(sc)
    r.controles = [
        Controle(controle_id=cid, version_regle="1", categorie="structure",
                 objets_controles=[], resultat=ResultatControle.NON_APPLICABLE, motif="")
        for cid in CONTROLES_OBLIGATOIRES
    ]
    assert r.accepte(sc) is False


def test_rapport_perime_apres_modification():
    sc = _scenario()
    e1 = empreinte_scenario(sc)
    sc2 = sc.model_copy(update={"domain": "autre_domaine"})
    e2 = empreinte_scenario(sc2)
    assert e1 != e2


def test_dependance_circulaire_detectee():
    from beaume.scenario.model import Calcul
    sc = _scenario(calculs=[
        Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["scn:calc:b", "1"]),
        Calcul(calcul_id="scn:calc:b", operation="somme_montants", arguments=["scn:calc:a", "1"]),
    ])
    r = valider_scenario(sc)
    c = [x for x in r.controles if x.controle_id == "structure.calculs_valides"][0]
    assert c.resultat is ResultatControle.ECHOUE



def _doc_with_champ(nom, valeur, type_champ="montant"):
    return {
        "document_id": "scn:doc:saisine",
        "titre": "t",
        "date": {"valeur": "2026-01-01", "precision": "jour"},
        "nature": "saisine",
        "auteur": "scn:actor:s",
        "assertions": [],
        "contenu": {
            "mode": "texte", "texte": "x",
            "champs": {nom: {"type": "litteral", "valeur": valeur}},
            "declarations": {nom: type_champ},
        },
        "provenance": _prov(),
    }


def test_montant_banane_rejete():
    r = valider_scenario(_scenario(documents=[_doc_with_champ("MONTANT", "banane")]))
    c = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_montant_nan_rejete():
    r = valider_scenario(_scenario(documents=[_doc_with_champ("MONTANT", "NaN")]))
    c = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_montant_infini_rejete():
    r = valider_scenario(_scenario(documents=[_doc_with_champ("MONTANT", "Infinity")]))
    c = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_montant_decimal_accepte():
    r = valider_scenario(_scenario(documents=[_doc_with_champ("MONTANT", "25000.00")]))
    c = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert c.resultat is ResultatControle.REUSSI


# --- Sous-lot B : references resolues ---

def test_destinataire_inexistant_rejete():
    doc = {
        "document_id": "scn:doc:saisine",
        "titre": "t",
        "date": {"valeur": "2026-01-01", "precision": "jour"},
        "nature": "saisine",
        "auteur": "scn:actor:s",
        "destinataire": "scn:actor:absent",
        "assertions": [],
        "contenu": {"mode": "texte", "texte": "x"},
        "provenance": _prov(),
    }
    r = valider_scenario(_scenario(documents=[doc]))
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.ECHOUE
    assert "destinataire" in c.motif


def test_provenance_repris_source_inexistante_rejetee():
    actors = [
        {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"],
         "provenance": {"mode": "repris", "source_id": "src:absent", "passage_exact": "p"}},
        {"actor_id": "scn:actor:e", "display_name": "E", "roles": ["defendeur"], "provenance": _prov()},
    ]
    r = valider_scenario(_scenario(actors=actors))
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.ECHOUE
    assert "src:absent" in c.motif


def test_provenance_repris_source_existante_acceptee():
    from beaume.scenario.model import Scenario
    sc = Scenario(
        schema_version="0.3",
        scenario_id="BEAUME-SC-0002-v1",
        scenario_version=1,
        partition="dev",
        domain="d",
        language="fr",
        created_at="2026-10-23",
        sources=[{"source_id": "src:ok", "kind": "decision_judiciaire"}],
        actors=[
            {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"],
             "provenance": {"mode": "repris", "source_id": "src:ok", "passage_exact": "p"}},
            {"actor_id": "scn:actor:e", "display_name": "E", "roles": ["defendeur"], "provenance": _prov()},
        ],
        events=[{"event_id": "scn:event:x",
                 "date": {"valeur": "2020-01-01", "precision": "jour"},
                 "description": "d", "actors_impliques": ["scn:actor:s"], "provenance": _prov()}],
        documents=[{"document_id": "scn:doc:saisine", "titre": "t",
                    "date": {"valeur": "2026-01-01", "precision": "jour"},
                    "nature": "saisine", "auteur": "scn:actor:s",
                    "assertions": [], "contenu": {"mode": "texte", "texte": "x"},
                    "provenance": _prov()}],
        propositions_juridiques=[],
    )
    r = valider_scenario(sc)
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.REUSSI


def test_provenance_calcule_operation_inconnue_rejetee():
    from beaume.scenario.model import Calcul
    actors = [
        {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"],
         "provenance": {"mode": "calcule", "operation": "eval", "dependances": ["scn:calc:a"]}},
        {"actor_id": "scn:actor:e", "display_name": "E", "roles": ["defendeur"], "provenance": _prov()},
    ]
    r = valider_scenario(_scenario(
        actors=actors,
        calculs=[Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["1", "1"])],
    ))
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.ECHOUE
    assert "eval" in c.motif


def test_provenance_calcule_dependance_absente_rejetee():
    from beaume.scenario.model import Calcul
    actors = [
        {"actor_id": "scn:actor:s", "display_name": "S", "roles": ["demandeur"],
         "provenance": {"mode": "calcule", "operation": "somme_montants", "dependances": ["scn:calc:absent"]}},
        {"actor_id": "scn:actor:e", "display_name": "E", "roles": ["defendeur"], "provenance": _prov()},
    ]
    r = valider_scenario(_scenario(
        actors=actors,
        calculs=[Calcul(calcul_id="scn:calc:a", operation="somme_montants", arguments=["1", "1"])],
    ))
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.ECHOUE
    assert "scn:calc:absent" in c.motif


# --- Sous-lot B : champs inconnus ---

def test_champ_inconnu_scenario_rejete():
    import pytest
    from pydantic import ValidationError
    from beaume.scenario.model import Scenario
    with pytest.raises(ValidationError, match="contraintes"):
        Scenario(
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
                     "description": "d", "actors_impliques": ["scn:actor:s"], "provenance": _prov()}],
            documents=[{"document_id": "scn:doc:saisine", "titre": "t",
                        "date": {"valeur": "2026-01-01", "precision": "jour"},
                        "nature": "saisine", "auteur": "scn:actor:s",
                        "assertions": [], "contenu": {"mode": "texte", "texte": "x"},
                        "provenance": _prov()}],
            propositions_juridiques=[],
            contraintes={"x": "y"},
        )


def test_champ_inconnu_acteur_rejete():
    import pytest
    from pydantic import ValidationError
    from beaume.scenario.model import Acteur
    with pytest.raises(ValidationError):
        Acteur(
            actor_id="scn:actor:s", display_name="S", roles=["demandeur"],
            provenance=_prov(), surnom="S2",
        )


def test_champ_inconnu_evenement_rejete():
    import pytest
    from pydantic import ValidationError
    from beaume.scenario.model import Evenement
    with pytest.raises(ValidationError):
        Evenement(
            event_id="scn:event:x",
            date={"valeur": "2020-01-01", "precision": "jour"},
            description="d", actors_impliques=["scn:actor:s"],
            provenance=_prov(), lieu="Paris",
        )


# --- Sous-lot C : accepte() strict + fraicheur ---

def test_tous_non_applicable_avec_motif_refuse():
    """A de l'audit : tous les obligatoires passes en non_applicable motive
    ne doivent plus suffire a accepter un rapport."""
    sc = _scenario()
    r = valider_scenario(sc)
    r.controles = [
        Controle(controle_id=cid, version_regle="1", categorie="structure",
                 objets_controles=[], resultat=ResultatControle.NON_APPLICABLE,
                 motif="motif quelconque")
        for cid in CONTROLES_OBLIGATOIRES
    ]
    assert r.accepte(sc) is False


def test_melange_reussi_non_applicable_refuse():
    sc = _scenario()
    r = valider_scenario(sc)
    ids = sorted(CONTROLES_OBLIGATOIRES)
    r.controles = [
        Controle(controle_id=cid, version_regle="1", categorie="structure",
                 objets_controles=[],
                 resultat=(ResultatControle.REUSSI if i == 0
                           else ResultatControle.NON_APPLICABLE),
                 motif="justifie")
        for i, cid in enumerate(ids)
    ]
    assert r.accepte(sc) is False


def test_tous_reussi_accepte():
    sc = _scenario()
    r = valider_scenario(sc)
    r.controles = [
        Controle(controle_id=cid, version_regle="1", categorie="structure",
                 objets_controles=[], resultat=ResultatControle.REUSSI, motif="")
        for cid in CONTROLES_OBLIGATOIRES
    ]
    assert r.accepte(sc) is True


def test_non_obligatoire_echoue_n_empeche_pas_acceptation():
    """Un controle hors obligatoires (ex: calculs_valides quand aucun calcul)
    peut etre non_applicable sans bloquer l'acceptation."""
    sc = _scenario()
    r = valider_scenario(sc)
    r.controles.append(
        Controle(controle_id="structure.calculs_valides", version_regle="1",
                 categorie="structure", objets_controles=[],
                 resultat=ResultatControle.NON_APPLICABLE,
                 motif="aucun calcul defini")
    )
    assert r.accepte(sc) is True


def test_fraicheur_empreinte_differente_refusee():
    sc = _scenario()
    r = valider_scenario(sc)
    sc2 = sc.model_copy(update={"scenario_version": 2})
    assert r.accepte(sc) is True
    assert r.accepte(sc2) is False



# --- F-a1 : litteral / reference / absent ---

def test_absent_accepte_quel_que_soit_le_type():
    doc = _doc_with_champ("MONTANT", "ignored", type_champ="montant")
    doc["contenu"]["champs"]["MONTANT"] = {
        "type": "absent", "motif": "non_defini_scenario",
    }
    r = valider_scenario(_scenario(documents=[doc]))
    c = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert c.resultat is ResultatControle.REUSSI


def test_litteral_date_invalide_rejetee():
    doc = _doc_with_champ("DATE_ACTUELLE", "pas-une-date", type_champ="date")
    r = valider_scenario(_scenario(documents=[doc]))
    c = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_litteral_entier_invalide_rejete():
    doc = _doc_with_champ("AGE", "vingt-cinq", type_champ="entier")
    r = valider_scenario(_scenario(documents=[doc]))
    c = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_declaration_sans_valeur_rejetee():
    doc = _doc_with_champ("MONTANT", "25000.00", type_champ="montant")
    doc["contenu"]["declarations"]["ORPHELIN"] = "texte"
    r = valider_scenario(_scenario(documents=[doc]))
    c = [x for x in r.controles if x.controle_id == "structure.declarations_champs"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_valeur_sans_declaration_rejetee():
    doc = _doc_with_champ("MONTANT", "25000.00", type_champ="montant")
    doc["contenu"]["champs"]["AUTRE"] = {"type": "litteral", "valeur": "x"}
    r = valider_scenario(_scenario(documents=[doc]))
    c = [x for x in r.controles if x.controle_id == "structure.declarations_champs"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_reference_actor_display_name_acceptee():
    doc = _doc_with_champ("NOM", "x", type_champ="texte")
    doc["contenu"]["champs"]["NOM"] = {
        "type": "reference", "cible": "scn:actor:s", "attribut": "display_name",
    }
    r = valider_scenario(_scenario(documents=[doc]))
    ref = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    val = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert ref.resultat is ResultatControle.REUSSI
    assert val.resultat is ResultatControle.REUSSI


def test_reference_actor_attribut_date_rejetee():
    # date n'est pas dans ATTRIBUTS_PAR_CIBLE["actor"]
    doc = _doc_with_champ("NOM", "x", type_champ="date")
    doc["contenu"]["champs"]["NOM"] = {
        "type": "reference", "cible": "scn:actor:s", "attribut": "date",
    }
    r = valider_scenario(_scenario(documents=[doc]))
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_reference_event_date_acceptee():
    doc = _doc_with_champ("DATE_EMBAUCHE", "x", type_champ="date")
    doc["contenu"]["champs"]["DATE_EMBAUCHE"] = {
        "type": "reference", "cible": "scn:event:x", "attribut": "date",
    }
    r = valider_scenario(_scenario(documents=[doc]))
    ref = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    val = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert ref.resultat is ResultatControle.REUSSI
    assert val.resultat is ResultatControle.REUSSI


def test_reference_calc_montant_accepte():
    from beaume.scenario.model import Calcul
    doc = _doc_with_champ("MONTANT", "x", type_champ="montant")
    doc["contenu"]["champs"]["MONTANT"] = {
        "type": "reference", "cible": "scn:calc:a", "attribut": "valeur",
    }
    sc = _scenario(
        documents=[doc],
        calculs=[Calcul(
            calcul_id="scn:calc:a", operation="somme_montants",
            arguments=["1", "1"],
        )],
    )
    r = valider_scenario(sc)
    val = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert val.resultat is ResultatControle.REUSSI


def test_reference_calc_type_incompatible_rejetee():
    from beaume.scenario.model import Calcul
    doc = _doc_with_champ("DATE_ACTUELLE", "x", type_champ="date")
    doc["contenu"]["champs"]["DATE_ACTUELLE"] = {
        "type": "reference", "cible": "scn:calc:a", "attribut": "valeur",
    }
    sc = _scenario(
        documents=[doc],
        calculs=[Calcul(
            calcul_id="scn:calc:a", operation="somme_montants",
            arguments=["1", "1"],
        )],
    )
    r = valider_scenario(sc)
    val = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert val.resultat is ResultatControle.ECHOUE


def test_reference_cible_inconnue_rejetee():
    doc = _doc_with_champ("NOM", "x", type_champ="texte")
    doc["contenu"]["champs"]["NOM"] = {
        "type": "reference", "cible": "scn:actor:absent",
        "attribut": "display_name",
    }
    r = valider_scenario(_scenario(documents=[doc]))
    val = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert val.resultat is ResultatControle.ECHOUE


# --- F-a1 : references_invoquees (audit B) ---

def _prop(references):
    return [{
        "proposition_id": "scn:prop:x",
        "type": "moyen",
        "contenu": "x",
        "statut_validation": "non_evaluee",
        "references_invoquees": references,
        "provenance": _prov(),
    }]


def test_references_invoquees_src_absent_rejetee():
    r = valider_scenario(_scenario(props=_prop(["src:absent"])))
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_references_invoquees_event_absent_rejetee():
    r = valider_scenario(_scenario(props=_prop(["scn:event:absent"])))
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.ECHOUE


def test_references_invoquees_type_non_supporte_rejetee():
    r = valider_scenario(_scenario(props=_prop(["foo:bar"])))
    c = [x for x in r.controles if x.controle_id == "structure.references_resolues"][0]
    assert c.resultat is ResultatControle.ECHOUE



# --- F-a2 : accepte() securise ---

def test_version_regle_obsolete_rejetee():
    sc = _scenario()
    r = valider_scenario(sc)
    for c in r.controles:
        c.version_regle = "0"
    assert r.accepte(sc) is False


def test_accepte_sans_scenario_echoue():
    sc = _scenario()
    r = valider_scenario(sc)
    try:
        r.accepte()
    except TypeError:
        return
    raise AssertionError("accepte() sans scenario aurait du echouer")


def test_controles_requis_sans_calculs():
    from beaume.scenario.validateur import (
        CONTROLES_OBLIGATOIRES as REQ_SANS_CALC,
        controles_requis,
    )
    assert controles_requis(_scenario()) == REQ_SANS_CALC


def test_controles_requis_avec_calculs():
    from beaume.scenario.model import Calcul
    from beaume.scenario.validateur import (
        CONTROLES_OBLIGATOIRES_AVEC_CALCULS as REQ_AVEC_CALC,
        controles_requis,
    )
    sc = _scenario(calculs=[Calcul(
        calcul_id="scn:calc:a", operation="somme_montants",
        arguments=["1", "1"],
    )])
    assert controles_requis(sc) == REQ_AVEC_CALC


def test_accepte_avec_calculs_exige_calculs_valides():
    from beaume.scenario.model import Calcul
    sc = _scenario(calculs=[Calcul(
        calcul_id="scn:calc:a", operation="somme_montants",
        arguments=["1", "1"],
    )])
    r = valider_scenario(sc)
    r.controles = [
        c for c in r.controles
        if c.controle_id != "structure.calculs_valides"
    ]
    assert r.accepte(sc) is False



# --- F-a2-beta1 : resolution effective des ValeurReference ---

def test_reference_calc_montant_resolue_reellement():
    from beaume.scenario.model import Calcul
    doc = _doc_with_champ("MONTANT", "x", type_champ="montant")
    doc["contenu"]["champs"]["MONTANT"] = {
        "type": "reference", "cible": "scn:calc:a", "attribut": "valeur",
    }
    sc = _scenario(
        documents=[doc],
        calculs=[Calcul(
            calcul_id="scn:calc:a", operation="somme_montants",
            arguments=["1", "1"],
        )],
    )
    r = valider_scenario(sc)
    val = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert val.resultat is ResultatControle.REUSSI


def test_reference_calc_echec_global_rejetee():
    # calcul a : valide
    # calcul b : depend d'un calcul absent -> resoudre_calculs global echoue
    from beaume.scenario.model import Calcul
    doc = _doc_with_champ("MONTANT", "x", type_champ="montant")
    doc["contenu"]["champs"]["MONTANT"] = {
        "type": "reference", "cible": "scn:calc:a", "attribut": "valeur",
    }
    sc = _scenario(
        documents=[doc],
        calculs=[
            Calcul(calcul_id="scn:calc:a", operation="somme_montants",
                   arguments=["1", "1"]),
            Calcul(calcul_id="scn:calc:b", operation="somme_montants",
                   arguments=["scn:calc:absent", "1"]),
        ],
    )
    r = valider_scenario(sc)
    val = [x for x in r.controles if x.controle_id == "structure.valeurs_champs"][0]
    assert val.resultat is ResultatControle.ECHOUE
    assert "calculs globaux invalides" in val.motif



# --- F-a2-beta2 : coherence provenance calcule <-> date du porteur ---

def test_coherence_date_calculee_correspond():
    from beaume.scenario.model import Calcul
    evt = {
        "event_id": "scn:event:x",
        "date": {"valeur": "2020-01-11", "precision": "jour"},
        "description": "d",
        "actors_impliques": ["scn:actor:s"],
        "provenance": {
            "mode": "calcule", "operation": "ajouter_jours",
            "dependances": ["scn:calc:a"],
        },
    }
    sc = _scenario(
        events=[evt],
        calculs=[Calcul(
            calcul_id="scn:calc:a", operation="ajouter_jours",
            arguments=["2020-01-01", "10"],
        )],
    )
    r = valider_scenario(sc)
    c = [x for x in r.controles
         if x.controle_id == "structure.coherence_dates_calculees"][0]
    assert c.resultat is ResultatControle.REUSSI
    assert r.accepte(sc) is True


def test_coherence_date_calculee_contradiction():
    from beaume.scenario.model import Calcul
    evt = {
        "event_id": "scn:event:x",
        "date": {"valeur": "2020-01-12", "precision": "jour"},
        "description": "d",
        "actors_impliques": ["scn:actor:s"],
        "provenance": {
            "mode": "calcule", "operation": "ajouter_jours",
            "dependances": ["scn:calc:a"],
        },
    }
    sc = _scenario(
        events=[evt],
        calculs=[Calcul(
            calcul_id="scn:calc:a", operation="ajouter_jours",
            arguments=["2020-01-01", "10"],
        )],
    )
    r = valider_scenario(sc)
    c = [x for x in r.controles
         if x.controle_id == "structure.coherence_dates_calculees"][0]
    assert c.resultat is ResultatControle.ECHOUE
    assert "incompatible" in c.motif
    assert r.accepte(sc) is False


def test_coherence_date_calculee_non_applicable_si_pas_calculs():
    r = valider_scenario(_scenario())
    c = [x for x in r.controles
         if x.controle_id == "structure.coherence_dates_calculees"][0]
    assert c.resultat is ResultatControle.NON_APPLICABLE


def test_coherence_date_calculee_dependance_non_date():
    from beaume.scenario.model import Calcul
    evt = {
        "event_id": "scn:event:x",
        "date": {"valeur": "2020-01-15", "precision": "jour"},
        "description": "d",
        "actors_impliques": ["scn:actor:s"],
        "provenance": {
            "mode": "calcule", "operation": "difference_jours",
            "dependances": ["scn:calc:a"],
        },
    }
    sc = _scenario(
        events=[evt],
        calculs=[Calcul(
            calcul_id="scn:calc:a", operation="difference_jours",
            arguments=["2020-01-15", "2020-01-01"],
        )],
    )
    r = valider_scenario(sc)
    c = [x for x in r.controles
         if x.controle_id == "structure.coherence_dates_calculees"][0]
    assert c.resultat is ResultatControle.ECHOUE
    assert "aucune dependance ne produit une date" in c.motif


def test_coherence_date_calculee_document():
    from beaume.scenario.model import Calcul
    doc = {
        "document_id": "scn:doc:conclusions_demandeur",
        "titre": "t",
        "date": {"valeur": "2020-01-31", "precision": "jour"},
        "nature": "conclusions",
        "auteur": "scn:actor:s",
        "assertions": [],
        "contenu": {"mode": "texte", "texte": "x"},
        "provenance": {
            "mode": "calcule", "operation": "ajouter_jours",
            "dependances": ["scn:calc:a"],
        },
    }
    sc = _scenario(
        documents=[doc],
        calculs=[Calcul(
            calcul_id="scn:calc:a", operation="ajouter_jours",
            arguments=["2020-01-01", "30"],
        )],
    )
    r = valider_scenario(sc)
    c = [x for x in r.controles
         if x.controle_id == "structure.coherence_dates_calculees"][0]
    assert c.resultat is ResultatControle.REUSSI


def test_coherence_multiple_dont_une_date_correspond():
    from beaume.scenario.model import Calcul
    evt = {
        "event_id": "scn:event:x",
        "date": {"valeur": "2020-01-11", "precision": "jour"},
        "description": "d",
        "actors_impliques": ["scn:actor:s"],
        "provenance": {
            "mode": "calcule", "operation": "ajouter_jours",
            "dependances": ["scn:calc:int", "scn:calc:date"],
        },
    }
    sc = _scenario(
        events=[evt],
        calculs=[
            Calcul(calcul_id="scn:calc:int",
                   operation="difference_jours",
                   arguments=["2020-01-11", "2020-01-01"]),
            Calcul(calcul_id="scn:calc:date",
                   operation="ajouter_jours",
                   arguments=["2020-01-01", "10"]),
        ],
    )
    r = valider_scenario(sc)
    c = [x for x in r.controles
         if x.controle_id == "structure.coherence_dates_calculees"][0]
    assert c.resultat is ResultatControle.REUSSI
