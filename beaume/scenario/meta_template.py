"""Metadonnees versionnees par template (schema_meta 1).

Chaque template a un fichier <template>.meta.json a cote de lui. Le
meta declare, pour chaque balise du template, son type et son statut
obligatoire. C'est l'unique source de verite : il n'y a pas de liste
separee de champs obligatoires.

Aucune coherence entre deux listes a maintenir : une seule cle
`champs`, chaque entree porte {type, obligatoire}. extra="forbid"
interdit les cles inattendues.

La validation verifie l'egalite exacte entre les cles `champs` et les
balises effectivement presentes dans le template (cf. verifier_templates).
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from beaume.scenario.champs import TypeChamp

SCHEMA_META_VERSION = "1"


class ChampMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: TypeChamp
    obligatoire: bool


class MetaTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_meta: str
    template: str
    champs: dict[str, ChampMeta] = Field(min_length=1)

    @field_validator("schema_meta")
    @classmethod
    def _version(cls, v: str) -> str:
        if v != SCHEMA_META_VERSION:
            raise ValueError(
                f"schema_meta attendu {SCHEMA_META_VERSION!r}, recu {v!r}"
            )
        return v


def nom_meta_pour(template_path: Path) -> Path:
    """Chemin du meta a cote d'un template : <template>.meta.json."""
    return template_path.with_name(template_path.name + ".meta.json")


def charger_meta(chemin: Path) -> MetaTemplate:
    """Charge et valide un meta. Leve OSError ou ValueError."""
    return MetaTemplate(**json.loads(chemin.read_text(encoding="utf-8")))
