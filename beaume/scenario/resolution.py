"""Resolveur commun validation / rendu.

Resout une ValeurReference vers une valeur typee reelle (str, date,
Decimal, int). N'evalue aucune chaine, ne fait aucun acces arbitraire
a des proprietes. Les attributs autorises par cible sont verifies par
le validateur (structure.references_resolues).

La reussite de la resolution ne prouve rien sur la verite juridique.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from beaume.scenario.calculs import (
    DependanceCirculaire,
    OperationInconnue,
    ReferenceAbsente,
    ResultatCalcul,
    TypeIncompatible,
    resoudre as resoudre_calculs,
)
from beaume.scenario.champs import AttributReference, ValeurReference
from beaume.scenario.model import Scenario


class ErreurResolution(Exception):
    """Echec de resolution d'une reference."""


ValeurResolue = str | date | Decimal | int


def _actor(scenario, cible):
    for a in scenario.actors:
        if a.actor_id == cible:
            return a
    raise ErreurResolution(f"acteur introuvable : {cible!r}")


def _event(scenario, cible):
    for e in scenario.events:
        if e.event_id == cible:
            return e
    raise ErreurResolution(f"evenement introuvable : {cible!r}")


def _doc(scenario, cible):
    for d in scenario.documents:
        if d.document_id == cible:
            return d
    raise ErreurResolution(f"document introuvable : {cible!r}")


def _calcul(scenario, cible):
    for c in scenario.calculs:
        if c.calcul_id == cible:
            return c
    raise ErreurResolution(f"calcul introuvable : {cible!r}")


def _calcul_depuis_resultat(rc: ResultatCalcul) -> ValeurResolue:
    if rc.type == "date":
        return date.fromisoformat(rc.valeur)
    if rc.type == "decimal":
        return Decimal(rc.valeur)
    if rc.type == "int":
        return int(rc.valeur)
    raise ErreurResolution(f"type de resultat inconnu : {rc.type!r}")


def resoudre_reference(
    ref: ValeurReference,
    scenario: Scenario,
    resultats_calculs: dict[str, ResultatCalcul] | None = None,
) -> ValeurResolue:
    """Resout une ValeurReference en une valeur typee.

    Verifie la cible et l'attribut, execute le calcul si necessaire,
    convertit le resultat au type Python attendu. Ne verifie pas que
    l'attribut est autorise pour le type de cible (c'est le role de
    structure.references_resolues) : un appel direct sur un attribut
    incoherent leve ErreurResolution.
    """
    cible = ref.cible
    attr = ref.attribut

    if cible.startswith("scn:actor:"):
        acteur = _actor(scenario, cible)
        if attr is AttributReference.DISPLAY_NAME:
            return acteur.display_name
        raise ErreurResolution(
            f"attribut {attr.value!r} non resolvable sur un acteur"
        )

    if cible.startswith("scn:event:"):
        evt = _event(scenario, cible)
        if attr is AttributReference.DATE:
            return evt.date.valeur
        if attr is AttributReference.DESCRIPTION:
            return evt.description
        raise ErreurResolution(
            f"attribut {attr.value!r} non resolvable sur un evenement"
        )

    if cible.startswith("scn:doc:"):
        doc = _doc(scenario, cible)
        if attr is AttributReference.DATE:
            return doc.date.valeur
        raise ErreurResolution(
            f"attribut {attr.value!r} non resolvable sur un document"
        )

    if cible.startswith("scn:calc:"):
        _calcul(scenario, cible)
        if attr is not AttributReference.VALEUR:
            raise ErreurResolution(
                f"attribut {attr.value!r} non resolvable sur un calcul"
            )
        if resultats_calculs is None:
            try:
                resultats_calculs = resoudre_calculs(scenario.calculs)
            except (ReferenceAbsente, DependanceCirculaire,
                    TypeIncompatible, OperationInconnue) as exc:
                raise ErreurResolution(
                    f"echec resolution calculs : {exc}"
                ) from exc
        if cible not in resultats_calculs:
            raise ErreurResolution(f"calcul {cible!r} non resolu")
        return _calcul_depuis_resultat(resultats_calculs[cible])

    raise ErreurResolution(f"cible de type inconnu : {cible!r}")
