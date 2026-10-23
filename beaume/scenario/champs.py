"""Valeurs de champ des contenus de documents (schema 0.3).

Trois variantes discriminees :
- litteral  : texte produit tel quel ;
- reference : pointe vers un acteur, un evenement, un document ou
              un calcul, avec un attribut dans une liste fermee ;
- absent    : absence declaree, avec motif explicite.

Aucun acces arbitraire a des proprietes. Aucun eval.
La validite structurelle d'une reference ne prouve pas sa valeur.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TypeChamp(str, Enum):
    TEXTE = "texte"
    DATE = "date"
    MONTANT = "montant"
    ENTIER = "entier"


class MotifAbsence(str, Enum):
    NON_DEFINI_SCENARIO = "non_defini_scenario"
    NON_RENSEIGNE_SOURCE = "non_renseigne_source"
    NON_PERTINENT = "non_pertinent"
    AUTRE = "autre"


class AttributReference(str, Enum):
    DISPLAY_NAME = "display_name"
    DATE = "date"
    DESCRIPTION = "description"
    VALEUR = "valeur"


class ValeurLitterale(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["litteral"]
    valeur: str = Field(min_length=1)

    @model_validator(mode="after")
    def _non_vide(self):
        # Decision H01 (audit lot F) : un litteral vide ou blanc est refuse ;
        # utiliser {"type": "absent", "motif": ...} a la place.
        if not self.valeur.strip():
            raise ValueError("litteral vide ou blanc refuse : declarer le champ absent")
        return self


class ValeurReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["reference"]
    cible: str
    attribut: AttributReference


class ValeurAbsente(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["absent"]
    motif: MotifAbsence
    precision: str | None = None

    @model_validator(mode="after")
    def _autre_explicite(self):
        if self.motif is MotifAbsence.AUTRE and not (self.precision or "").strip():
            raise ValueError("absent motif=autre : precision (texte explicatif) requise")
        return self


ValeurChamp = Annotated[
    Union[ValeurLitterale, ValeurReference, ValeurAbsente],
    Field(discriminator="type"),
]


# Attributs autorises par type de cible (verifies par le validateur).
# Volontairement restreint : pas d'acces a `roles` (liste) ni
# `actors_impliques` (liste) dans un champ texte mono-valeur.
ATTRIBUTS_PAR_CIBLE: dict[str, frozenset[AttributReference]] = {
    "actor": frozenset({AttributReference.DISPLAY_NAME}),
    "event": frozenset({AttributReference.DATE, AttributReference.DESCRIPTION}),
    "doc": frozenset({AttributReference.DATE}),
    "calc": frozenset({AttributReference.VALEUR}),
}

# Type effectif d'un attribut independamment du type de cible.
# `calc/valeur` est absent : depend du type de sortie du calcul,
# verifie au validateur.
TYPE_EFFECTIF_ATTRIBUT: dict[AttributReference, TypeChamp] = {
    AttributReference.DISPLAY_NAME: TypeChamp.TEXTE,
    AttributReference.DATE: TypeChamp.DATE,
    AttributReference.DESCRIPTION: TypeChamp.TEXTE,
}
