"""Validateur JSON Schema restreint au sous-ensemble Beaume.

Vérifie toutes les contraintes du sous-ensemble, y compris celles qui ne
sont PAS dans la grammaire GBNF (uniqueItems, additionalProperties, bornes
minItems/maxItems, enum). Aucune dépendance externe (jsonschema absent).

Sépare explicitement :
- json_parse_valide : la sortie est-elle un JSON parsable ?
- schema_technique_valide : les contraintes du schéma sont-elles respectées ?
- schema_metier_valide : TOUJOURS None. L'exactitude sémantique n'est pas
  établie par la validation technique.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ResultatValidation:
    json_parse_valide: bool
    schema_technique_valide: bool
    violations: list[str] = field(default_factory=list)
    schema_metier_valide: Optional[bool] = None
    valeur: Optional[Any] = None
    erreur_parse: Optional[str] = None


def valider(texte: str, schema: dict) -> ResultatValidation:
    """Parse le texte, valide contre le schéma, retourne un résultat structuré.

    Ne lève pas d'exception sur données invalides : tout est dans le résultat.
    """
    try:
        valeur = json.loads(texte)
    except json.JSONDecodeError as e:
        return ResultatValidation(
            json_parse_valide=False,
            schema_technique_valide=False,
            erreur_parse=str(e),
        )
    violations: list[str] = []
    _valider_valeur(valeur, schema, "$", violations)
    return ResultatValidation(
        json_parse_valide=True,
        schema_technique_valide=len(violations) == 0,
        violations=violations,
        valeur=valeur,
    )


def _valider_valeur(valeur, schema, chemin, violations):
    """Valide récursivement. Ajoute les violations à la liste, ne lève rien."""
    if not isinstance(schema, dict):
        violations.append(f"{chemin}: schéma invalide (pas un objet)")
        return
    enum = schema.get("enum")
    if enum is not None:
        t_enum = schema.get("type")
        # Vérification de type AVANT l'appartenance, pour ne pas confondre
        # True avec 1 (en Python, True == 1 et True in [1] est True).
        if t_enum == "integer":
            if isinstance(valeur, bool) or not isinstance(valeur, int):
                violations.append(
                    f"{chemin}: attendu integer (enum), "
                    f"reçu {type(valeur).__name__}"
                )
                return
        elif t_enum == "number":
            if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
                violations.append(
                    f"{chemin}: attendu number (enum), "
                    f"reçu {type(valeur).__name__}"
                )
                return
        elif t_enum == "string":
            if not isinstance(valeur, str):
                violations.append(
                    f"{chemin}: attendu string (enum), "
                    f"reçu {type(valeur).__name__}"
                )
                return
        if not _valeur_dans_enum(valeur, enum):
            violations.append(f"{chemin}: {valeur!r} hors enum {enum!r}")
        return
    t = schema.get("type")
    if t == "object":
        if not isinstance(valeur, dict):
            violations.append(f"{chemin}: attendu object, reçu {type(valeur).__name__}")
            return
        _valider_object(valeur, schema, chemin, violations)
        return
    if t == "array":
        if not isinstance(valeur, list):
            violations.append(f"{chemin}: attendu array, reçu {type(valeur).__name__}")
            return
        _valider_array(valeur, schema, chemin, violations)
        return
    if t == "string":
        if not isinstance(valeur, str):
            violations.append(f"{chemin}: attendu string, reçu {type(valeur).__name__}")
        return
    if t == "integer":
        # bool est un sous-type d'int en Python : on l'exclut explicitement.
        if isinstance(valeur, bool) or not isinstance(valeur, int):
            violations.append(f"{chemin}: attendu integer, reçu {type(valeur).__name__}")
        return
    if t == "number":
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            violations.append(f"{chemin}: attendu number, reçu {type(valeur).__name__}")
        return
    if t == "boolean":
        if not isinstance(valeur, bool):
            violations.append(f"{chemin}: attendu boolean, reçu {type(valeur).__name__}")
        return
    if t is None:
        # Pas de contrainte de type : tout est accepté (sous-schéma {}).
        return
    violations.append(f"{chemin}: type inconnu : {t!r}")


def _valider_object(valeur, schema, chemin, violations):
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    for nom in required:
        if nom not in valeur:
            violations.append(f"{chemin}: propriété requise absente : {nom!r}")
    for nom, sous in props.items():
        if nom in valeur:
            _valider_valeur(valeur[nom], sous, f"{chemin}.{nom}", violations)
    if schema.get("additionalProperties") is False:
        inconnues = set(valeur.keys()) - set(props.keys())
        if inconnues:
            violations.append(
                f"{chemin}: propriétés non autorisées : {sorted(inconnues)}"
            )


def _cle_unique(valeur):
    """Clé hashable pour uniqueItems. Distingue 1 et True, 1 et 1.0."""
    if isinstance(valeur, bool):
        return ("bool", valeur)
    if isinstance(valeur, (int, float)):
        return ("num", valeur)
    if isinstance(valeur, str):
        return ("str", valeur)
    return ("json", json.dumps(valeur, sort_keys=True, ensure_ascii=False))


def _valider_array(valeur, schema, chemin, violations):
    min_i = schema.get("minItems")
    max_i = schema.get("maxItems")
    if isinstance(min_i, int) and len(valeur) < min_i:
        violations.append(
            f"{chemin}: {len(valeur)} éléments < minItems={min_i}"
        )
    if isinstance(max_i, int) and len(valeur) > max_i:
        violations.append(
            f"{chemin}: {len(valeur)} éléments > maxItems={max_i}"
        )
    if schema.get("uniqueItems") is True:
        vues = {}
        for i, v in enumerate(valeur):
            k = _cle_unique(v)
            if k in vues:
                violations.append(
                    f"{chemin}: uniqueItems violé "
                    f"(index {vues[k]} et {i})"
                )
            else:
                vues[k] = i
    items = schema.get("items")
    if isinstance(items, dict):
        for i, v in enumerate(valeur):
            _valider_valeur(v, items, f"{chemin}[{i}]", violations)


def _valeur_dans_enum(valeur, enum):
    """Appartenance stricte, en distinguant bool et int via _cle_unique."""
    k = _cle_unique(valeur)
    return any(_cle_unique(v) == k for v in enum)
