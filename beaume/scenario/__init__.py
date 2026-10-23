"""Scenarios fictifs Beaume : contrat type et validation structurelle (schema 0.2)."""
from beaume.scenario.champs import (
    AttributReference,
    MotifAbsence,
    TypeChamp,
    ValeurAbsente,
    ValeurChamp,
    ValeurLitterale,
    ValeurReference,
)
from beaume.scenario.model import (
    Acteur,
    Calcul,
    Assertion,
    DateScn,
    Document,
    Evenement,
    ModeProvenance,
    Montant,
    PorteeAssertion,
    PrecisionDate,
    Proposition,
    Provenance,
    Scenario,
    StatutProposition,
)
from beaume.scenario.rapport import Controle, RapportValidation, ResultatControle
from beaume.scenario.resolution import ErreurResolution, resoudre_reference
from beaume.scenario.validateur import (
    CONTROLES_OBLIGATOIRES,
    CONTROLES_OBLIGATOIRES_AVEC_CALCULS,
    controles_requis,
    valider_scenario,
)

__all__ = [
    "Acteur", "Assertion", "AttributReference", "Calcul", "Controle",
    "MotifAbsence", "TypeChamp", "ValeurAbsente", "ValeurChamp",
    "ValeurLitterale", "ValeurReference",
    "CONTROLES_OBLIGATOIRES", "CONTROLES_OBLIGATOIRES_AVEC_CALCULS",
    "controles_requis",
    "DateScn", "Document", "Evenement", "ModeProvenance", "Montant",
    "PorteeAssertion", "PrecisionDate", "Proposition", "Provenance",
    "RapportValidation", "ResultatControle", "Scenario", "StatutProposition",
    "ErreurResolution", "resoudre_reference",
    "valider_scenario",
]
