"""Schemas JSON transmis a Ollama pour le constrained decoding.

Separe du generateur pour eviter un cycle d'import entre
beaume.application.analyse_dossier et beaume.adapters.generateur_ollama.
Le schema n'est pas une affaire d'adaptateur : c'est le contrat de
sortie de l'analyse.

Constats du 2026-10-16 sur dossier_gros_001 :
- "code" doit etre un enum : sinon Qwen colle le numero dedans
  ("code_travail L2282-2").
- "fichier" doit etre un enum SANS "" : si on laisse "" dans la
  liste, Qwen choisit "" pour toutes les citations. Si on retire
  "", Qwen est force de choisir un vrai fichier.
- "pages" doit etre un enum des pages REELLES : avec un simple
  "type: integer", Qwen invente "1234", "5678", etc. en concatenant
  des numeros.
"""
from __future__ import annotations

import copy
from typing import Any

from beaume.legal.model import CodeJuridique

_CODES_VALIDES: list[str] = [c.value for c in CodeJuridique]


SCHEMA_ANALYSE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "contexte": {"type": "string"},
        "parties": {"type": "array", "items": {"type": "string"}},
        "demandes": {"type": "array", "items": {"type": "string"}},
        "problemes_juridiques": {
            "type": "array",
            "items": {"type": "string"},
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "enum": _CODES_VALIDES,
                    },
                    "numero": {"type": "string"},
                    "extrait": {"type": "string"},
                    "pages": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "fichier": {"type": "string"},
                },
                "required": ["code", "numero"],
            },
        },
    },
    "required": ["contexte", "citations"],
}


def schema_analyse_avec_fichiers(
    fichiers: tuple[str, ...],
    pages_max: int = 1,
) -> dict[str, Any]:
    """Retourne une copie de SCHEMA_ANALYSE avec "fichier" enumere.

    - "fichier" : enum des vrais noms, sans "".
    - "pages" : enum des pages disponibles (1..pages_max), minItems 1.

    Si aucun fichier n'est fourni, on retourne SCHEMA_ANALYSE tel quel.
    """
    schema = copy.deepcopy(SCHEMA_ANALYSE)
    if not fichiers:
        return schema

    pages_valides = list(range(1, max(1, pages_max) + 1))

    item = schema["properties"]["citations"]["items"]
    item["properties"]["fichier"] = {
        "type": "string",
        "enum": list(fichiers),
    }
    item["properties"]["pages"] = {
        "type": "array",
        "items": {"type": "integer", "enum": pages_valides},
        "minItems": 1,
    }
    item["required"] = ["code", "numero", "fichier", "pages"]
    return schema