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

Refonte du 2026-10-19 : sur les cinq dossiers du bench, le modele
choisissait le bon article mais recopiait un extrait qui n'existait
pas dans le texte officiel (statut texte_different). On ne demande
plus au modele de recopier le texte de loi. Il selectionne un
article_id parmi les candidats fournis, et l'application hydrate
l'extrait depuis SQLite. Voir analyse_dossier._hydrater_citation.
"""
from __future__ import annotations

import copy
from typing import Any


# Sentinelle utilisee quand aucun article n'est disponible. Elle ne
# doit jamais apparaitre dans une Citation retournee : analyse_dossier
# la rejette. Elle existe uniquement pour que le schema Ollama reste
# syntaxiquement valide (un enum vide n'est pas acceptable).
_SENTINELLE_AUCUN_ARTICLE = "__AUCUN__"


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
                    "article_id": {
                        "type": "string",
                        "enum": [_SENTINELLE_AUCUN_ARTICLE],
                    },
                    "fichier": {"type": "string"},
                    "pages": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["article_id"],
            },
        },
    },
    "required": ["contexte", "citations"],
}


def schema_analyse_avec_candidats(
    article_ids: tuple[str, ...],
    fichiers: tuple[str, ...],
    pages_max: int = 1,
) -> dict[str, Any]:
    """Retourne une copie de SCHEMA_ANALYSE configuree pour ce dossier.

    - "article_id" : enum des article_id candidats. Si la liste est
      vide, l'enum contient uniquement la sentinelle __AUCUN__.
    - "fichier" : enum des vrais noms de fichiers, sans "".
    - "pages" : enum des pages disponibles (1..pages_max), minItems 1,
      maxItems 5, uniqueItems.

    Si aucun fichier n'est fourni, "fichier" et "pages" restent au
    type libre et ne sont pas requis. Cette situation ne devrait pas
    arriver en pipeline nominal (tout dossier a au moins un PDF lu).
    """
    schema = copy.deepcopy(SCHEMA_ANALYSE)
    item = schema["properties"]["citations"]["items"]

    ids_effectifs = list(article_ids) if article_ids else [_SENTINELLE_AUCUN_ARTICLE]
    item["properties"]["article_id"]["enum"] = ids_effectifs

    if fichiers:
        pages_valides = list(range(1, max(1, pages_max) + 1))
        item["properties"]["fichier"] = {
            "type": "string",
            "enum": list(fichiers),
        }
        item["properties"]["pages"] = {
            "type": "array",
            "items": {"type": "integer", "enum": pages_valides},
            "minItems": 1,
            "maxItems": 5,
            "uniqueItems": True,
        }
        item["required"] = ["article_id", "fichier", "pages"]

    return schema


# Compatibilite descendante : certains tests et modules importent
# l'ancien nom. Le nouveau nom est explicite sur la presence d'une
# liste de candidats. L'ancien nom est conserve pour ne pas casser
# les imports existants, mais il delegue au nouveau avec une liste
# vide (schema sans enum d'article_id valide).
def schema_analyse_avec_fichiers(
    fichiers: tuple[str, ...],
    pages_max: int = 1,
    article_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    return schema_analyse_avec_candidats(
        article_ids=article_ids,
        fichiers=fichiers,
        pages_max=pages_max,
    )