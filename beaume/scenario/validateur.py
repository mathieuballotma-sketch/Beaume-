"""Validateur structurel d'un scenario fictif Beaume (schema 0.3).

Ne verifie ni la verite juridique, ni la coherence factuelle avec une
source externe. Verifie les controles structurels listes dans
CONTROLES_OBLIGATOIRES. La validite structurelle d'une provenance
ou d'une reference ne prouve pas son contenu.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from beaume.scenario.calculs import (
    DependanceCirculaire,
    OPERATIONS,
    OperationInconnue,
    ReferenceAbsente,
    TypeIncompatible,
    resoudre as resoudre_calculs,
)
from beaume.scenario.champs import (
    ATTRIBUTS_PAR_CIBLE,
    TYPE_EFFECTIF_ATTRIBUT,
    TypeChamp,
    ValeurAbsente,
    ValeurLitterale,
    ValeurReference,
)
from beaume.scenario.resolution import (
    ErreurResolution,
    resoudre_reference,
)
from beaume.scenario.meta_template import (
    charger_meta,
    nom_meta_pour,
)
from beaume.scenario.model import ModeProvenance, Scenario
from beaume.scenario.rapport import Controle, RapportValidation, ResultatControle

# "2" : formats litteraux stricts, dates_valides effectif,
# auteur != destinataire (audit lot F, 2026-10-23).
VERSION_REGLE = "6"  # 6 : empreintes_meta exhaustives ; F-b3b

# Hypotheses de contrat (a confirmer par Mathieu) :
# montant = chiffres ASCII, point decimal, 2 decimales max, >= 0, 15 chiffres max ;
# entier = chiffres ASCII avec signe '-' optionnel ; date = AAAA-MM-JJ.
_RE_MONTANT = re.compile(r"\A[0-9]{1,15}(\.[0-9]{1,2})?\Z")
_RE_ENTIER = re.compile(r"\A-?[0-9]{1,9}\Z")
_RE_DATE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_RE_BALISE = re.compile(r"\[([A-Z0-9_]+)\]")

CONTROLES_OBLIGATOIRES: set[str] = {
    "structure.ids_uniques",
    "structure.references_resolues",
    "structure.provenance_complete",
    "structure.dates_valides",
    "scenario.evenements_chronologiques",
    "structure.declarations_champs",
    "structure.valeurs_champs",
    "scenario.acteurs_roles_coherents",
}

CONTROLES_OBLIGATOIRES_AVEC_CALCULS: set[str] = CONTROLES_OBLIGATOIRES | {
    "structure.calculs_valides",
    "structure.coherence_dates_calculees",
}


def controles_requis(scenario: Scenario) -> set[str]:
    base = (
        CONTROLES_OBLIGATOIRES_AVEC_CALCULS
        if scenario.calculs
        else CONTROLES_OBLIGATOIRES
    )
    requis = set(base)
    if any(d.contenu.mode == "template" for d in scenario.documents):
        requis.add("generation.templates_coherents")
    if any(
        nom.startswith(("NOM_", "AVOCAT_"))
        for d in scenario.documents
        for nom in d.contenu.champs
    ):
        requis.add("structure.balises_roles")
    return requis

TYPE_SORTIE_CALC: dict[str, TypeChamp] = {
    "ajouter_jours": TypeChamp.DATE,
    "soustraire_jours": TypeChamp.DATE,
    "difference_jours": TypeChamp.ENTIER,
    "multiplier_montant": TypeChamp.MONTANT,
    "somme_montants": TypeChamp.MONTANT,
}

TYPE_PYTHON_PAR_CHAMP: dict[TypeChamp, type] = {
    TypeChamp.TEXTE: str,
    TypeChamp.DATE: date,
    TypeChamp.MONTANT: Decimal,
    TypeChamp.ENTIER: int,
}


def empreinte_scenario(scenario: Scenario) -> str:
    canonique = json.dumps(
        scenario.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()


def _c(controle_id: str, resultat: ResultatControle, objets: list[str],
       motif: str = "") -> Controle:
    return Controle(
        controle_id=controle_id,
        version_regle=VERSION_REGLE,
        categorie=controle_id.split(".", 1)[0],
        objets_controles=objets,
        resultat=resultat,
        motif=motif,
    )


def _ids_uniques(scenario: Scenario) -> Controle:
    vus: dict[str, str] = {}
    doublons: list[str] = []
    objets: list[str] = []
    groupes = [
        ("actor", [a.actor_id for a in scenario.actors]),
        ("event", [e.event_id for e in scenario.events]),
        ("doc", [d.document_id for d in scenario.documents]),
        ("source", [s.source_id for s in scenario.sources]),
    ]
    for _kind, ids in groupes:
        for i in ids:
            objets.append(i)
            if i in vus:
                doublons.append(i)
            vus[i] = _kind
    for d in scenario.documents:
        for a in d.assertions:
            objets.append(a.assertion_id)
            if a.assertion_id in vus:
                doublons.append(a.assertion_id)
            vus[a.assertion_id] = "assert"
    for p in scenario.propositions_juridiques:
        objets.append(p.proposition_id)
        if p.proposition_id in vus:
            doublons.append(p.proposition_id)
        vus[p.proposition_id] = "prop"
    for c in scenario.calculs:
        objets.append(c.calcul_id)
        if c.calcul_id in vus:
            doublons.append(c.calcul_id)
        vus[c.calcul_id] = "calc"
    if doublons:
        return _c(
            "structure.ids_uniques",
            ResultatControle.ECHOUE,
            objets,
            f"identifiants dupliques : {sorted(set(doublons))}",
        )
    return _c("structure.ids_uniques", ResultatControle.REUSSI, objets)


def _toutes_les_provenances(scenario: Scenario):
    for a in scenario.actors:
        yield a.actor_id, a.provenance
    for e in scenario.events:
        yield e.event_id, e.provenance
    for d in scenario.documents:
        yield d.document_id, d.provenance
        for a in d.assertions:
            yield a.assertion_id, a.provenance
    for p in scenario.propositions_juridiques:
        yield p.proposition_id, p.provenance


def _references_resolues(scenario: Scenario) -> Controle:
    actor_ids = {a.actor_id for a in scenario.actors}
    doc_ids = {d.document_id for d in scenario.documents}
    source_ids = {s.source_id for s in scenario.sources}
    calcul_ids = {c.calcul_id for c in scenario.calculs}
    event_ids = {e.event_id for e in scenario.events}
    objets: list[str] = []
    manquants: list[str] = []
    for e in scenario.events:
        objets.extend(e.actors_impliques)
        for ref in e.actors_impliques:
            if ref not in actor_ids:
                manquants.append(f"{e.event_id}->{ref}")
    for d in scenario.documents:
        objets.append(d.auteur)
        if d.auteur not in actor_ids:
            manquants.append(f"{d.document_id}.auteur->{d.auteur}")
        if d.destinataire is not None:
            objets.append(d.destinataire)
            if d.destinataire not in actor_ids:
                manquants.append(f"{d.document_id}.destinataire->{d.destinataire}")
        for a in d.assertions:
            objets.append(a.acteur_source)
            if a.acteur_source not in actor_ids:
                manquants.append(
                    f"{a.assertion_id}.acteur_source->{a.acteur_source}"
                )
    for p in scenario.propositions_juridiques:
        for ref in p.references_invoquees:
            objets.append(ref)
            if ref.startswith("src:"):
                if ref not in source_ids:
                    manquants.append(f"{p.proposition_id}->{ref}")
            elif ref.startswith("scn:doc:"):
                if ref not in doc_ids:
                    manquants.append(f"{p.proposition_id}->{ref}")
            elif ref.startswith("scn:event:"):
                if ref not in event_ids:
                    manquants.append(f"{p.proposition_id}->{ref}")
            elif ref.startswith("scn:calc:"):
                if ref not in calcul_ids:
                    manquants.append(f"{p.proposition_id}->{ref}")
            else:
                manquants.append(f"{p.proposition_id}->{ref} (type non supporte)")
    for obj_id, prov in _toutes_les_provenances(scenario):
        if prov.mode in (ModeProvenance.REPRIS, ModeProvenance.TRANSFORME):
            if prov.source_id is not None:
                objets.append(prov.source_id)
                if prov.source_id not in source_ids:
                    manquants.append(
                        f"{obj_id}.provenance.source_id->{prov.source_id}"
                    )
        elif prov.mode is ModeProvenance.CALCULE:
            if prov.operation is not None:
                objets.append(prov.operation)
                if prov.operation not in OPERATIONS:
                    manquants.append(
                        f"{obj_id}.provenance.operation inconnu {prov.operation!r}"
                    )
            for dep in prov.dependances:
                objets.append(dep)
                if dep not in calcul_ids:
                    manquants.append(
                        f"{obj_id}.provenance.dependances->{dep}"
                    )
    for d in scenario.documents:
        for nom_champ, val in d.contenu.champs.items():
            if not isinstance(val, ValeurReference):
                continue
            kind = (
                "actor" if val.cible.startswith("scn:actor:")
                else "event" if val.cible.startswith("scn:event:")
                else "doc" if val.cible.startswith("scn:doc:")
                else "calc" if val.cible.startswith("scn:calc:")
                else None
            )
            if kind is None:
                manquants.append(
                    f"{d.document_id}.{nom_champ}.cible type inconnu {val.cible!r}"
                )
                continue
            if val.attribut not in ATTRIBUTS_PAR_CIBLE.get(kind, frozenset()):
                manquants.append(
                    f"{d.document_id}.{nom_champ}.attribut "
                    f"{val.attribut.value!r} non autorise sur {kind}"
                )
    if manquants:
        return _c(
            "structure.references_resolues",
            ResultatControle.ECHOUE,
            objets,
            f"references non resolues : {manquants}",
        )
    return _c("structure.references_resolues", ResultatControle.REUSSI, objets)


def _provenance_complete(scenario: Scenario) -> Controle:
    objets: list[str] = []
    incompletes: list[str] = []
    for oid, prov in _toutes_les_provenances(scenario):
        objets.append(oid)
        if prov is None:
            incompletes.append(oid)
    if incompletes:
        return _c(
            "structure.provenance_complete",
            ResultatControle.ECHOUE,
            objets,
            f"provenances manquantes : {incompletes}",
        )
    return _c("structure.provenance_complete", ResultatControle.REUSSI, objets)


def _dates_valides(scenario: Scenario) -> Controle:
    """Aucune date d'evenement ou de document posterieure a created_at."""
    limite = scenario.created_at.valeur
    objets: list[str] = []
    echecs: list[str] = []
    datees = [(e.event_id, e.date.valeur) for e in scenario.events] + [
        (d.document_id, d.date.valeur) for d in scenario.documents
    ]
    for oid, d in datees:
        objets.append(oid)
        if d > limite:
            echecs.append(f"{oid}: {d.isoformat()} posterieure a created_at {limite.isoformat()}")
    if echecs:
        return _c("structure.dates_valides", ResultatControle.ECHOUE, objets, " ; ".join(echecs))
    return _c("structure.dates_valides", ResultatControle.REUSSI, objets)


def _cible_existe(cible: str, scenario: Scenario) -> bool:
    if cible.startswith("scn:actor:"):
        return any(a.actor_id == cible for a in scenario.actors)
    if cible.startswith("scn:event:"):
        return any(e.event_id == cible for e in scenario.events)
    if cible.startswith("scn:doc:"):
        return any(doc.document_id == cible for doc in scenario.documents)
    return False


def _type_effectif_reference(ref: ValeurReference, calculs_par_id) -> TypeChamp | None:
    if ref.cible.startswith("scn:calc:"):
        if ref.cible not in calculs_par_id:
            return None
        calcul = calculs_par_id[ref.cible]
        if calcul.operation not in OPERATIONS:
            return None
        return TYPE_SORTIE_CALC.get(calcul.operation)
    return TYPE_EFFECTIF_ATTRIBUT.get(ref.attribut)


def _declarations_champs(scenario: Scenario) -> Controle:
    objets: list[str] = []
    echecs: list[str] = []
    for d in scenario.documents:
        decl = set(d.contenu.declarations.keys())
        val = set(d.contenu.champs.keys())
        objets.extend(f"{d.document_id}.{k}" for k in sorted(decl | val))
        for k in sorted(decl - val):
            echecs.append(f"{d.document_id}.{k}: declare sans valeur")
        for k in sorted(val - decl):
            echecs.append(f"{d.document_id}.{k}: valeur sans declaration")
    if echecs:
        return _c(
            "structure.declarations_champs",
            ResultatControle.ECHOUE,
            objets,
            "; ".join(echecs),
        )
    return _c("structure.declarations_champs", ResultatControle.REUSSI, objets)


def _valeurs_champs(scenario: Scenario) -> Controle:
    calculs_par_id = {c.calcul_id: c for c in scenario.calculs}
    resultats_calculs = {}
    erreur_calculs_globale = None
    if scenario.calculs:
        try:
            resultats_calculs = resoudre_calculs(scenario.calculs)
        except (ReferenceAbsente, DependanceCirculaire,
                TypeIncompatible, OperationInconnue) as exc:
            erreur_calculs_globale = f"{type(exc).__name__}: {exc}"
    objets: list[str] = []
    echecs: list[str] = []
    for d in scenario.documents:
        for nom_champ, valeur in d.contenu.champs.items():
            ref = f"{d.document_id}.{nom_champ}"
            objets.append(ref)
            attendu = d.contenu.declarations.get(nom_champ)
            if attendu is None:
                continue
            if isinstance(valeur, ValeurAbsente):
                continue
            if isinstance(valeur, ValeurLitterale):
                try:
                    brut = valeur.valeur
                    if attendu is TypeChamp.MONTANT and not _RE_MONTANT.match(brut):
                        raise ValueError("format montant attendu : 1234 ou 1234.56")
                    if attendu is TypeChamp.ENTIER and not _RE_ENTIER.match(brut):
                        raise ValueError("format entier attendu : chiffres ASCII")
                    if attendu is TypeChamp.DATE and not _RE_DATE.match(brut):
                        raise ValueError("format date attendu : AAAA-MM-JJ")
                    if attendu is TypeChamp.MONTANT:
                        v = Decimal(valeur.valeur)
                        if not v.is_finite():
                            raise ValueError("valeur non finie")
                    elif attendu is TypeChamp.ENTIER:
                        int(valeur.valeur)
                    elif attendu is TypeChamp.DATE:
                        date.fromisoformat(valeur.valeur)
                except (InvalidOperation, ValueError, TypeError) as exc:
                    echecs.append(
                        f"{ref}={valeur.valeur!r} invalide ({exc})"
                    )
                continue
            if isinstance(valeur, ValeurReference):
                cible_ok = (
                    valeur.cible in calculs_par_id
                    or _cible_existe(valeur.cible, scenario)
                )
                if not cible_ok:
                    echecs.append(f"{ref}.cible inconnue {valeur.cible!r}")
                    continue
                type_eff = _type_effectif_reference(valeur, calculs_par_id)
                if type_eff is None:
                    echecs.append(
                        f"{ref}.attribut {valeur.attribut.value!r} non typable"
                    )
                    continue
                if type_eff != attendu:
                    echecs.append(
                        f"{ref}: type effectif {type_eff.value} "
                        f"incompatible avec declaration {attendu.value}"
                    )
                    continue
                if (valeur.cible.startswith("scn:calc:")
                        and erreur_calculs_globale is not None):
                    echecs.append(
                        f"{ref}: calculs globaux invalides "
                        f"({erreur_calculs_globale})"
                    )
                    continue
                try:
                    val_resolue = resoudre_reference(
                        valeur, scenario,
                        resultats_calculs=resultats_calculs,
                    )
                except ErreurResolution as exc:
                    echecs.append(
                        f"{ref}: resolution echouee ({exc})"
                    )
                    continue
                py_attendu = TYPE_PYTHON_PAR_CHAMP[attendu]
                if not isinstance(val_resolue, py_attendu):
                    echecs.append(
                        f"{ref}: type python {type(val_resolue).__name__} "
                        f"inattendu pour declaration {attendu.value}"
                    )
    if echecs:
        return _c(
            "structure.valeurs_champs",
            ResultatControle.ECHOUE,
            objets,
            "; ".join(echecs),
        )
    return _c("structure.valeurs_champs", ResultatControle.REUSSI, objets)


def _acteurs_roles_coherents(scenario: Scenario) -> Controle:
    objets = [a.actor_id for a in scenario.actors]
    demandeurs = [a for a in scenario.actors if "demandeur" in a.roles]
    defendeurs = [a for a in scenario.actors if "defendeur" in a.roles]
    motifs: list[str] = []
    if not demandeurs:
        motifs.append("aucun acteur avec role 'demandeur'")
    if not defendeurs:
        motifs.append("aucun acteur avec role 'defendeur'")
    if len(demandeurs) > 1:
        motifs.append(f"plusieurs demandeurs : {[a.actor_id for a in demandeurs]}")
    if len(defendeurs) > 1:
        motifs.append(f"plusieurs defendeurs : {[a.actor_id for a in defendeurs]}")
    for d in scenario.documents:
        if d.destinataire is not None and d.destinataire == d.auteur:
            motifs.append(f"{d.document_id}: auteur == destinataire ({d.auteur})")
    if motifs:
        return _c(
            "scenario.acteurs_roles_coherents",
            ResultatControle.ECHOUE,
            objets,
            " ; ".join(motifs),
        )
    return _c("scenario.acteurs_roles_coherents", ResultatControle.REUSSI, objets)


def _calculs_valides(scenario: Scenario) -> Controle:
    if not scenario.calculs:
        return _c(
            "structure.calculs_valides",
            ResultatControle.NON_APPLICABLE,
            [],
            "aucun calcul defini",
        )
    ids = [c.calcul_id for c in scenario.calculs]
    try:
        resoudre_calculs(scenario.calculs)
        return _c("structure.calculs_valides", ResultatControle.REUSSI, ids)
    except (ReferenceAbsente, DependanceCirculaire, TypeIncompatible, OperationInconnue) as exc:
        return _c(
            "structure.calculs_valides",
            ResultatControle.ECHOUE,
            ids,
            f"{type(exc).__name__}: {exc}",
        )


def _verifier_coherence_date(
    id_obj: str,
    date_porteur,
    prov,
    resultats,
    objets: list[str],
    echecs: list[str],
) -> None:
    if prov.mode is not ModeProvenance.CALCULE:
        return
    objets.append(id_obj)
    dates_produites = [
        date.fromisoformat(resultats[dep].valeur)
        for dep in prov.dependances
        if dep in resultats and resultats[dep].type == "date"
    ]
    if not dates_produites:
        echecs.append(f"{id_obj}: aucune dependance ne produit une date")
        return
    if date_porteur not in dates_produites:
        echecs.append(
            f"{id_obj}: date {date_porteur.isoformat()} incompatible avec "
            f"{[d.isoformat() for d in dates_produites]}"
        )


def _coherence_dates_calculees(scenario: Scenario) -> Controle:
    if not scenario.calculs:
        return _c(
            "structure.coherence_dates_calculees",
            ResultatControle.NON_APPLICABLE,
            [],
            "aucun calcul defini",
        )
    try:
        resultats = resoudre_calculs(scenario.calculs)
    except (ReferenceAbsente, DependanceCirculaire,
            TypeIncompatible, OperationInconnue) as exc:
        return _c(
            "structure.coherence_dates_calculees",
            ResultatControle.INDETERMINE,
            [],
            f"calculs non resolus ({type(exc).__name__}): {exc}",
        )
    objets: list[str] = []
    echecs: list[str] = []
    for evt in scenario.events:
        _verifier_coherence_date(
            evt.event_id, evt.date.valeur, evt.provenance,
            resultats, objets, echecs,
        )
    for doc in scenario.documents:
        _verifier_coherence_date(
            doc.document_id, doc.date.valeur, doc.provenance,
            resultats, objets, echecs,
        )
    if echecs:
        return _c(
            "structure.coherence_dates_calculees",
            ResultatControle.ECHOUE,
            objets,
            " ; ".join(echecs),
        )
    return _c(
        "structure.coherence_dates_calculees",
        ResultatControle.REUSSI,
        objets,
    )


def verifier_templates(scenario: Scenario, racine: Path) -> Controle:
    """Controle documentaire des templates et de leurs metas (F-b3a).

    Facettes de motif (prefixes) :
    - [chemin]        : template hors data/scenarios/structures/
    - [absent]        : template ou meta introuvable
    - [meta_invalide] : meta illisible ou Pydantic refuse
    - [meta_template] : meta.template != nom de fichier du template
    - [parite]        : meta / template / scenario non concordants
    - [type]          : type declare dans le scenario != type du meta
    - [obligatoire]   : champ obligatoire du meta declare absent dans le
                        scenario

    Fail-closed : toute incoherence est un ECHOUE, jamais un REUSSI tacite.
    """
    base = (racine / "data" / "scenarios" / "structures").resolve()
    objets: list[str] = []
    echecs: list[str] = []
    for d in scenario.documents:
        if d.contenu.mode != "template":
            continue
        objets.append(d.document_id)
        chemin = (racine / d.contenu.chemin).resolve()
        if base not in chemin.parents:
            echecs.append(
                f"[chemin] {d.document_id}: hors structures {d.contenu.chemin!r}"
            )
            continue
        if not chemin.is_file():
            echecs.append(
                f"[absent] {d.document_id}: template introuvable {d.contenu.chemin!r}"
            )
            continue
        meta_chemin = nom_meta_pour(chemin)
        if not meta_chemin.is_file():
            echecs.append(
                f"[absent] {d.document_id}: meta introuvable {meta_chemin.name}"
            )
            continue
        try:
            meta = charger_meta(meta_chemin)
        except (OSError, ValueError) as exc:
            echecs.append(
                f"[meta_invalide] {d.document_id}: {exc}"
            )
            continue
        if meta.template != chemin.name:
            echecs.append(
                f"[meta_template] {d.document_id}: meta.template={meta.template!r} "
                f"!= {chemin.name!r}"
            )
            continue
        balises = set(_RE_BALISE.findall(chemin.read_text(encoding="utf-8")))
        meta_champs = set(meta.champs)
        if meta_champs - balises:
            echecs.append(
                f"[parite] {d.document_id}: meta declare "
                f"{sorted(meta_champs - balises)} absent(s) du template"
            )
        if balises - meta_champs:
            echecs.append(
                f"[parite] {d.document_id}: template a "
                f"{sorted(balises - meta_champs)} absent(s) du meta"
            )
        champs_scenario = set(d.contenu.champs)
        if balises - champs_scenario:
            echecs.append(
                f"[parite] {d.document_id}: balises du template sans champ "
                f"{sorted(balises - champs_scenario)}"
            )
        if champs_scenario - balises:
            echecs.append(
                f"[parite] {d.document_id}: champs du scenario sans balise "
                f"{sorted(champs_scenario - balises)}"
            )
        decl = d.contenu.declarations
        for k, champ_meta in meta.champs.items():
            if k in decl and decl[k] != champ_meta.type.value:
                echecs.append(
                    f"[type] {d.document_id}.{k}: declaration={decl[k]!r} "
                    f"!= meta={champ_meta.type.value!r}"
                )
            if champ_meta.obligatoire and k in d.contenu.champs:
                val = d.contenu.champs[k]
                if isinstance(val, ValeurAbsente):
                    echecs.append(
                        f"[obligatoire] {d.document_id}.{k}: "
                        f"obligatoire declare absent"
                    )
    if not objets:
        return _c("generation.templates_coherents", ResultatControle.NON_APPLICABLE,
                  [], "aucun document template")
    res = ResultatControle.ECHOUE if echecs else ResultatControle.REUSSI
    return _c("generation.templates_coherents", res, objets, " ; ".join(echecs))


def _balises_roles(scenario: Scenario) -> Controle:
    """Convention H03 : tout champ NOM_<suffixe> doit etre une
    ValeurReference vers un acteur dont les roles contiennent
    <suffixe.lower()>. Detecte les inversions demandeur/defendeur.
    """
    objets: list[str] = []
    echecs: list[str] = []
    for d in scenario.documents:
        for nom_champ, valeur in d.contenu.champs.items():
            if nom_champ.startswith("NOM_"):
                suffixe = nom_champ[4:].lower()
            elif nom_champ.startswith("AVOCAT_"):
                # AVOCAT_DEMANDEUR -> role avocat_demandeur ; absent tolere
                # (avocat non defini), litteral refuse comme pour NOM_.
                suffixe = nom_champ.lower()
                if isinstance(valeur, ValeurAbsente):
                    continue
            else:
                continue
            ref = f"{d.document_id}.{nom_champ}"
            objets.append(ref)
            if not isinstance(valeur, ValeurReference):
                echecs.append(
                    f"{ref}: doit etre une reference a un acteur, "
                    f"pas {valeur.type}"
                )
                continue
            if not valeur.cible.startswith("scn:actor:"):
                echecs.append(
                    f"{ref}: cible {valeur.cible!r} n'est pas un acteur"
                )
                continue
            acteur = next(
                (a for a in scenario.actors if a.actor_id == valeur.cible),
                None,
            )
            if acteur is None:
                echecs.append(
                    f"{ref}: acteur {valeur.cible!r} introuvable"
                )
                continue
            if suffixe not in acteur.roles:
                echecs.append(
                    f"{ref}: suffixe {suffixe!r} absent des roles "
                    f"{acteur.roles} de {acteur.actor_id}"
                )
    if not objets:
        return _c(
            "structure.balises_roles",
            ResultatControle.NON_APPLICABLE,
            [],
            "aucun champ NOM_ ou AVOCAT_ renseigne",
        )
    res = ResultatControle.ECHOUE if echecs else ResultatControle.REUSSI
    return _c("structure.balises_roles", res, objets, " ; ".join(echecs))


def _evenements_chronologiques(scenario: Scenario) -> Controle:
    """Verifie que scenario.events est trie par date croissante.

    Option 1 (arbitrage du 23/10) : ordre declaratif, pas de semantique
    de "relate_events". Les dates egales sont autorisees. Moins de deux
    evenements : rien a ordonner, REUSSI.
    """
    objets = [e.event_id for e in scenario.events]
    if len(scenario.events) < 2:
        return _c(
            "scenario.evenements_chronologiques",
            ResultatControle.REUSSI,
            objets,
        )
    for i in range(1, len(scenario.events)):
        precedent = scenario.events[i - 1]
        courant = scenario.events[i]
        if courant.date.valeur < precedent.date.valeur:
            return _c(
                "scenario.evenements_chronologiques",
                ResultatControle.ECHOUE,
                objets,
                f"{courant.event_id} ({courant.date.valeur.isoformat()}) "
                f"anterieur a {precedent.event_id} "
                f"({precedent.date.valeur.isoformat()})",
            )
    return _c(
        "scenario.evenements_chronologiques",
        ResultatControle.REUSSI,
        objets,
    )


def valider_scenario(
    scenario: Scenario,
    racine=None,
) -> RapportValidation:
    controles = [
        _evenements_chronologiques(scenario),
        _ids_uniques(scenario),
        _references_resolues(scenario),
        _provenance_complete(scenario),
        _dates_valides(scenario),
        _declarations_champs(scenario),
        _valeurs_champs(scenario),
        _acteurs_roles_coherents(scenario),
        _calculs_valides(scenario),
        _coherence_dates_calculees(scenario),
        _balises_roles(scenario),
    ]
    empreintes_templates: dict[str, str] = {}
    empreintes_meta: dict[str, str] = {}
    has_templates = any(
        d.contenu.mode == "template" for d in scenario.documents
    )
    if has_templates:
        if racine is None:
            controles.append(
                _c(
                    "generation.templates_coherents",
                    ResultatControle.INDETERMINE,
                    [],
                    "racine requise pour verifier les templates",
                )
            )
        else:
            controles.append(verifier_templates(scenario, racine))
            base = (racine / "data" / "scenarios" / "structures").resolve()
            for d in scenario.documents:
                if d.contenu.mode != "template":
                    continue
                chemin = (racine / d.contenu.chemin).resolve()
                if base in chemin.parents and chemin.is_file():
                    empreintes_templates[d.contenu.chemin] = hashlib.sha256(
                        chemin.read_bytes()
                    ).hexdigest()
                    meta_chemin = nom_meta_pour(chemin)
                    if meta_chemin.is_file():
                        empreintes_meta[
                            d.contenu.chemin + ".meta.json"
                        ] = hashlib.sha256(
                            meta_chemin.read_bytes()
                        ).hexdigest()
    return RapportValidation(
        rapport_id=f"rapport:{scenario.scenario_id}:v{scenario.scenario_version}",
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        schema_version=scenario.schema_version,
        empreinte_scenario=empreinte_scenario(scenario),
        genere_le=datetime.now(timezone.utc),
        controles=controles,
        empreintes_templates=empreintes_templates,
        empreintes_meta=empreintes_meta,
    )
