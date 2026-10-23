"""Contrat typé des scénarios fictifs Beaume (schema_version 0.3).

Trois niveaux strictement séparés :
- réalité fictive interne : acteurs et événements qui ont eu lieu ;
- assertions documentaires : ce qu'une partie affirme dans une pièce ;
- propositions juridiques : qualifications, moyens, conclusions.

La provenance est attachée au conteneur (acteur, événement, assertion,
document, proposition). Les champs obligatoires dépendent du mode.
Un champ rempli n'est pas une provenance vérifiée.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from beaume.scenario.champs import TypeChamp, ValeurChamp

SCHEMA_VERSION = "0.3"


class ModeProvenance(str, Enum):
    REPRIS = "repris"
    TRANSFORME = "transforme"
    CREE = "cree"
    CALCULE = "calcule"


class PrecisionDate(str, Enum):
    JOUR = "jour"
    MOIS = "mois"
    ANNEE = "annee"


class PorteeAssertion(str, Enum):
    FAIT_ALLEGUE = "fait_allegue"
    FAIT_CONTESTE = "fait_conteste"
    FAIT_ETABLI = "fait_etabli"
    ARGUMENT_JURIDIQUE = "argument_juridique"


class RoleActeur(str, Enum):
    """Roles fermes d'un acteur. Un role inconnu est refuse
    au parsing : il doit etre ajoute explicitement au contrat."""
    DEMANDEUR = "demandeur"
    DEFENDEUR = "defendeur"
    SALARIE = "salarie"
    EMPLOYEUR = "employeur"
    AVOCAT_DEMANDEUR = "avocat_demandeur"
    AVOCAT_DEFENDEUR = "avocat_defendeur"
    TEMOIN = "temoin"


class StatutProposition(str, Enum):
    NON_EVALUEE = "non_evaluee"
    EN_ATTENTE = "en_attente"
    VALIDEE = "validee"
    REJETEE = "rejetee"


class DateScn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    valeur: date
    precision: PrecisionDate = PrecisionDate.JOUR

    @field_validator("valeur", mode="before")
    @classmethod
    def _iso(cls, v):
        if isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError as exc:
                raise ValueError(f"Date ISO AAAA-MM-JJ attendue : {v!r}") from exc
        return v


def _date_scn_before(v):
    if isinstance(v, str):
        return {"valeur": v, "precision": PrecisionDate.JOUR}
    return v


DateScnField = Annotated[DateScn, BeforeValidator(_date_scn_before)]


class Montant(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    valeur: Decimal
    devise: Literal["EUR"] = "EUR"

    @field_validator("valeur", mode="before")
    @classmethod
    def _exact(cls, v):
        if isinstance(v, float):
            raise ValueError("Montant : float refusé, utiliser une chaîne décimale exacte")
        if isinstance(v, str):
            try:
                return Decimal(v)
            except InvalidOperation as exc:
                raise ValueError(f"Montant décimal invalide : {v!r}") from exc
        return v

    @field_validator("valeur")
    @classmethod
    def _positif(cls, v):
        if v < 0:
            raise ValueError(f"Montant négatif refusé : {v}")
        return v


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: ModeProvenance
    source_id: str | None = None
    passage_exact: str | None = None
    transformation: str | None = None
    regle: str | None = None
    parametres: dict = Field(default_factory=dict)
    operation: str | None = None
    dependances: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherence(self):
        if self.mode is ModeProvenance.REPRIS:
            if not self.source_id or not self.passage_exact:
                raise ValueError("provenance repris : source_id et passage_exact requis")
        elif self.mode is ModeProvenance.TRANSFORME:
            if not self.source_id or not self.transformation:
                raise ValueError("provenance transforme : source_id et transformation requis")
        elif self.mode is ModeProvenance.CREE:
            if not self.regle:
                raise ValueError("provenance cree : regle requise")
        elif self.mode is ModeProvenance.CALCULE:
            if not self.operation or not self.dependances:
                raise ValueError("provenance calcule : operation et dependances requis")
        return self


class Acteur(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str
    display_name: str
    roles: list[RoleActeur] = Field(min_length=1)
    provenance: Provenance

    @field_validator("actor_id")
    @classmethod
    def _prefixe(cls, v):
        if not v.startswith("scn:actor:"):
            raise ValueError(f"actor_id doit commencer par 'scn:actor:' : {v!r}")
        return v


class Evenement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    date: DateScnField
    description: str
    actors_impliques: list[str] = Field(min_length=1)
    provenance: Provenance

    @field_validator("event_id")
    @classmethod
    def _prefixe(cls, v):
        if not v.startswith("scn:event:"):
            raise ValueError(f"event_id doit commencer par 'scn:event:' : {v!r}")
        return v


class Assertion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assertion_id: str
    contenu: str
    portee: PorteeAssertion
    acteur_source: str
    provenance: Provenance

    @field_validator("assertion_id")
    @classmethod
    def _prefixe(cls, v):
        if not v.startswith("scn:assert:"):
            raise ValueError(f"assertion_id doit commencer par 'scn:assert:' : {v!r}")
        return v


class ContenuDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["template", "texte"]
    chemin: str | None = None
    texte: str | None = None
    champs: dict[str, ValeurChamp] = Field(default_factory=dict)
    declarations: dict[str, TypeChamp] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _coherence(self):
        if self.mode == "template" and not self.chemin:
            raise ValueError("contenu mode=template : chemin requis")
        if self.mode == "texte" and not self.texte:
            raise ValueError("contenu mode=texte : texte requis")
        return self


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    titre: str
    date: DateScnField
    nature: str
    auteur: str
    destinataire: str | None = None
    assertions: list[Assertion] = Field(default_factory=list)
    contenu: ContenuDocument
    provenance: Provenance

    @field_validator("document_id")
    @classmethod
    def _prefixe(cls, v):
        if not v.startswith("scn:doc:"):
            raise ValueError(f"document_id doit commencer par 'scn:doc:' : {v!r}")
        return v


class Proposition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposition_id: str
    type: Literal["qualification", "moyen", "conclusion"]
    contenu: str
    statut_validation: StatutProposition = StatutProposition.NON_EVALUEE
    references_invoquees: list[str] = Field(default_factory=list)
    provenance: Provenance

    @field_validator("proposition_id")
    @classmethod
    def _prefixe(cls, v):
        if not v.startswith("scn:prop:"):
            raise ValueError(f"proposition_id doit commencer par 'scn:prop:' : {v!r}")
        return v


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    kind: str
    juridiction: str | None = None
    date: DateScnField | None = None
    note: str | None = None

    @field_validator("source_id")
    @classmethod
    def _prefixe(cls, v):
        if not v.startswith("src:"):
            raise ValueError(f"source_id doit commencer par 'src:' : {v!r}")
        return v


class Calcul(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calcul_id: str
    operation: str
    arguments: list[str] = Field(min_length=1)

    @field_validator("calcul_id")
    @classmethod
    def _prefixe(cls, v):
        if not v.startswith("scn:calc:"):
            raise ValueError(f"calcul_id doit commencer par 'scn:calc:' : {v!r}")
        return v


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["0.3"]
    scenario_id: str
    scenario_version: int
    partition: Literal["dev", "test", "train"]
    domain: str
    language: Literal["fr"]
    created_at: DateScnField
    sources: list[Source] = Field(default_factory=list)
    actors: list[Acteur]
    events: list[Evenement]
    documents: list[Document]
    calculs: list[Calcul] = Field(default_factory=list)
    propositions_juridiques: list[Proposition] = Field(default_factory=list)

    @field_validator("scenario_id")
    @classmethod
    def _format(cls, v):
        if not v.startswith("BEAUME-SC-"):
            raise ValueError(f"scenario_id doit commencer par 'BEAUME-SC-' : {v!r}")
        return v
