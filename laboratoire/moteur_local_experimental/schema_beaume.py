"""Convertisseur JSON Schema -> GBNF restreint au sous-ensemble du schéma
Beaume. Refuse explicitement tout mot-clé non convertible ET non vérifiable
après génération. Les contraintes convertibles sont dans la grammaire ; les
contraintes vérifiables après génération (uniqueItems) sont exclues de la
grammaire et vérifiées par validateur_beaume."""

from __future__ import annotations
import itertools
from typing import Any, Optional

# Mots-clés acceptés par le convertisseur (convertibles en GBNF).
_CLES_CONVERTIBLES = frozenset({
    "type", "properties", "items", "required", "additionalProperties",
    "enum", "minItems", "maxItems",
})
# Mots-clés acceptés mais NON convertibles : vérifiés après génération.
_CLES_VERIFIEES_APRES = frozenset({"uniqueItems"})
# Types supportés par la grammaire.
_TYPES_SUPPORTES = frozenset({
    "object", "array", "string", "integer", "number", "boolean",
})

_MAX_OPTIONNELS_GBNF = 4  # 2**4 = 16 combinaisons max


class SchemaNonSupporte(ValueError):
    """Levée quand le schéma contient un mot-clé hors sous-ensemble."""


def _inspecter(schema: Any, chemin: str = "$") -> list[str]:
    """Retourne la liste des chemins de contraintes vérifiées après génération.

    Lève SchemaNonSupporte si un mot-clé est inconnu, non convertible et non
    vérifiable après. Ne descend que dans les sous-schémas pertinents.
    """
    if not isinstance(schema, dict):
        raise SchemaNonSupporte(
            f"{chemin}: le schéma doit être un objet, reçu {type(schema).__name__}"
        )
    inconnues = set(schema.keys()) - _CLES_CONVERTIBLES - _CLES_VERIFIEES_APRES
    if inconnues:
        raise SchemaNonSupporte(
            f"{chemin}: mot(s)-clé(s) non supporté(s) : {sorted(inconnues)}"
        )
    verifiees: list[str] = []
    if schema.get("uniqueItems") is True:
        if schema.get("type") != "array":
            raise SchemaNonSupporte(
                f"{chemin}: uniqueItems n'a de sens que sur un array"
            )
        verifiees.append(chemin)
    t = schema.get("type")
    if t is not None and t not in _TYPES_SUPPORTES:
        raise SchemaNonSupporte(
            f"{chemin}: type non supporté : {t!r}"
        )
    if t == "object":
        props = schema.get("properties")
        if not isinstance(props, dict) or not props:
            raise SchemaNonSupporte(
                f"{chemin}: object doit avoir properties non vide"
            )
        for nom, sous in props.items():
            verifiees.extend(_inspecter(sous, f"{chemin}.{nom}"))
        req = schema.get("required")
        if req is not None:
            if not isinstance(req, list) or not all(
                isinstance(x, str) for x in req
            ):
                raise SchemaNonSupporte(
                    f"{chemin}: required doit être une liste de chaînes"
                )
            inconnues_req = [x for x in req if x not in props]
            if inconnues_req:
                raise SchemaNonSupporte(
                    f"{chemin}: required inconnus : {inconnues_req}"
                )
    elif t == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            raise SchemaNonSupporte(
                f"{chemin}: array doit avoir items objet"
            )
        verifiees.extend(_inspecter(items, f"{chemin}[]"))
    enum = schema.get("enum")
    if enum is not None:
        if not isinstance(enum, list) or not enum:
            raise SchemaNonSupporte(
                f"{chemin}: enum doit être une liste non vide"
            )
        for v in enum:
            if not isinstance(v, (str, int, bool)):
                raise SchemaNonSupporte(
                    f"{chemin}: enum supporte seulement str/int/bool"
                )
    return verifiees


def contraintes_verifiees_apres_generation(schema: dict) -> list[str]:
    """Retourne les chemins JSON des contraintes non convertibles.

    Lève SchemaNonSupporte si le schéma sort du sous-ensemble.
    """
    return _inspecter(schema)


# Règles GBNF pour les chaînes JSON (Unicode + échappements), alignées sur
# premier_moteur.REGLES_CHAINE_JSON.
_REGLES_CHAINE = (
    r'chaine   ::= "\"" ch* "\""' + "\n"
    r'ch       ::= [^"\\\x00-\x1F\x7F] | "\\" esc' + "\n"
    r'esc      ::= ["\\/bfnrt] | "u" hx hx hx hx' + "\n"
    r'hx       ::= [0-9a-fA-F]' + "\n"
)


def _gbnf_enum_str(valeurs):
    """Construit une alternative GBNF pour des valeurs littérales (str/int/bool)."""
    alts = []
    for v in valeurs:
        if isinstance(v, bool):
            alts.append('"true"' if v else '"false"')
        elif isinstance(v, int):
            alts.append('"' + str(v) + '"')
        else:
            echappe = v.replace("\\", "\\\\").replace('"', '\\"')
            alts.append('"\\"' + echappe + '\\""')
    if len(alts) == 1:
        return alts[0]
    return "(" + " | ".join(alts) + ")"


def _gbnf_entier_borne(enum_vals):
    """GBNF pour un entier dont les seules valeurs autorisées sont enum_vals."""
    if not enum_vals:
        return '"0"'
    mini = min(enum_vals)
    maxi = max(enum_vals)
    if mini >= 0:
        return '[0-9]{1,10}'
    return '"-"? [0-9]{1,10}'


def _gbnf_valeur(schema, indent):
    """GBNF pour un sous-schéma. Suppose _inspecter() déjà appelé sans erreur.

    Tableaux : règle récursive (0+ éléments). minItems/maxItems/uniqueItems
    sont vérifiés par validateur_beaume, PAS par la grammaire.
    Objets : toutes les combinaisons de propriétés optionnelles sont générées
    (pas seulement les préfixes). Refus explicite au-delà de
    _MAX_OPTIONNELS_GBNF optionnels, pour éviter une grammaire ingérable.
    additionalProperties n'est pas contraint par la grammaire ; le validateur
    le vérifie.
    """
    t = schema.get("type")
    enum = schema.get("enum")

    if enum is not None:
        if t in ("integer", "number"):
            return _gbnf_entier_borne(enum)
        return _gbnf_enum_str(enum)

    if t == "string":
        return "chaine"
    if t == "integer":
        return '"-"' + "? [0-9]{1,10}"
    if t == "number":
        return '"-"' + "? [0-9]{1,10}" + ' ("." [0-9]{1,10})?'
    if t == "boolean":
        return '("true" | "false")'
    if t == "array":
        sous = _gbnf_valeur(schema["items"], indent + 2)
        return (
            '("[]" | "[" ws ' + sous
            + ' (ws "," ws ' + sous + ')* ws "]")'
        )
    if t == "object":
        props = schema["properties"]
        required = set(schema.get("required", []))
        req_paires = []
        opt_paires = []
        for nom, sous in props.items():
            val = _gbnf_valeur(sous, indent + 2)
            paire = '"\\"' + nom + '\\""' + ' ws ":" ws ' + val
            if nom in required:
                req_paires.append(paire)
            else:
                opt_paires.append(paire)
        if len(opt_paires) > _MAX_OPTIONNELS_GBNF:
            raise SchemaNonSupporte(
                "trop d'optionnels pour une grammaire fidèle : "
                + str(len(opt_paires))
                + " > "
                + str(_MAX_OPTIONNELS_GBNF)
            )
        alts = []
        for k in range(0, len(opt_paires) + 1):
            for comb in itertools.combinations(range(len(opt_paires)), k):
                paires = list(req_paires) + [opt_paires[i] for i in comb]
                corps = ' ws "," ws '.join(paires)
                alts.append('"{" ws ' + corps + ' ws "}"')
        if len(alts) == 1:
            return alts[0]
        return "(" + " | ".join(alts) + ")"
    raise SchemaNonSupporte("type non supporté pour GBNF : " + repr(t))

def generer_gbnf(schema):
    """Convertit un schéma Beaume en GBNF.

    Lève SchemaNonSupporte si le schéma sort du sous-ensemble. Les contraintes
    listées par contraintes_verifiees_apres_generation() ne sont PAS dans la
    grammaire ; elles doivent être vérifiées par validateur_beaume.
    """
    _inspecter(schema)  # validation stricte en amont
    corps = _gbnf_valeur(schema, 0)
    return (
        "root ::= ws " + corps + " ws" + "\n"
        "ws   ::= [ \\t\\n]{0,4}" + "\n"
        + _REGLES_CHAINE
    )
