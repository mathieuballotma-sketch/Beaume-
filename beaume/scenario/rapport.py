"""Rapport de validation separe du scenario."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResultatControle(str, Enum):
    REUSSI = "reussi"
    ECHOUE = "echoue"
    INDETERMINE = "indetermine"
    NON_APPLICABLE = "non_applicable"


class Controle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    controle_id: str
    version_regle: str
    categorie: Literal["structure", "scenario", "generation", "juridique"]
    objets_controles: list[str]
    resultat: ResultatControle
    motif: str = ""


class RapportValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rapport_id: str
    scenario_id: str
    scenario_version: int
    schema_version: str
    empreinte_scenario: str
    genere_le: datetime
    controles: list[Controle] = Field(default_factory=list)

    def accepte(
        self,
        scenario,
        obligatoires: set[str] | None = None,
    ) -> bool:
        """Verdict d'acceptation. Le scenario est obligatoire.

        - l'empreinte du scenario est confrontee a celle du rapport ;
        - les controles requis sont determines automatiquement ;
        - chaque controle obligatoire doit etre reussi ET porte
          la version de regle attendue par le code courant.
        """
        from beaume.scenario.validateur import (
            VERSION_REGLE,
            controles_requis,
            empreinte_scenario,
        )
        if empreinte_scenario(scenario) != self.empreinte_scenario:
            return False
        # `obligatoires` peut AJOUTER des controles, jamais en retirer.
        requis = controles_requis(scenario) | (obligatoires or set())
        presents = {c.controle_id for c in self.controles}
        if not requis <= presents:
            return False
        for c in self.controles:
            if c.controle_id not in requis:
                continue
            if c.resultat is not ResultatControle.REUSSI:
                return False
            if c.version_regle != VERSION_REGLE:
                return False
        return True
