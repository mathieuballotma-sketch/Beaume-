"""Rapport de validation separe du scenario."""
from __future__ import annotations

import hashlib
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
    empreintes_templates: dict[str, str] = Field(default_factory=dict)
    empreintes_meta: dict[str, str] = Field(default_factory=dict)

    def accepte(
        self,
        scenario,
        obligatoires: set[str] | None = None,
        racine=None,
    ) -> bool:
        """Verdict d'acceptation. Le scenario est obligatoire.

        - l'empreinte du scenario est confrontee a celle du rapport ;
        - si le scenario contient un template, le rapport doit porter
          les empreintes des templates et racine doit etre fourni pour
          les recalculer ; toute divergence invalide le rapport ;
        - les controles requis sont determines automatiquement ;
        - chaque controle obligatoire doit etre reussi ET porte la
          version de regle attendue par le code courant.
        """
        from beaume.scenario.validateur import (
            VERSION_REGLE,
            controles_requis,
            empreinte_scenario,
        )
        if empreinte_scenario(scenario) != self.empreinte_scenario:
            return False
        has_templates = any(
            d.contenu.mode == "template" for d in scenario.documents
        )
        if has_templates:
            if not self.empreintes_templates:
                return False
            if racine is None:
                return False
            attendus = {
                d.contenu.chemin for d in scenario.documents
                if d.contenu.mode == "template"
            }
            # Le rapport doit couvrir exactement les templates du scenario.
            if set(self.empreintes_templates) != attendus:
                return False
            base = (racine / "data" / "scenarios" / "structures").resolve()
            for rel_chemin, h_stored in self.empreintes_templates.items():
                chemin = (racine / rel_chemin).resolve()
                if base not in chemin.parents:
                    return False
                if not chemin.is_file():
                    return False
                if hashlib.sha256(chemin.read_bytes()).hexdigest() != h_stored:
                    return False
            # Empreintes de metas (F-b3b, symetrique aux templates).
            if not self.empreintes_meta:
                return False
            attendus_m = {a + ".meta.json" for a in attendus}
            if set(self.empreintes_meta) != attendus_m:
                return False
            for rel_chemin, h_stored in self.empreintes_meta.items():
                chemin = (racine / rel_chemin).resolve()
                if base not in chemin.parents:
                    return False
                if not chemin.is_file():
                    return False
                if hashlib.sha256(chemin.read_bytes()).hexdigest() != h_stored:
                    return False
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
