"""Registre ferme d'operations explicites pour les calculs de scenario.

Pas d'eval, pas d'execution de chaine. Operations whitelistees.
Chaque operation declare sa signature (types par position). Un
argument est soit une reference a un autre calcul (prefixe
"scn:calc:"), soit un litteral (date ISO, entier, decimal fini).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Callable, Literal, Union

from pydantic import BaseModel, ConfigDict

from beaume.scenario.model import Calcul

Valeur = Union[date, Decimal, int]


class ErreurCalcul(Exception):
    """Base des erreurs de calcul."""


class OperationInconnue(ErreurCalcul):
    pass


class ReferenceAbsente(ErreurCalcul):
    pass


class DependanceCirculaire(ErreurCalcul):
    pass


class TypeIncompatible(ErreurCalcul):
    pass


def _op_ajouter_jours(a, b):
    return a + timedelta(days=b)


def _op_soustraire_jours(a, b):
    return a - timedelta(days=b)


def _op_difference_jours(a, b):
    return (a - b).days


def _op_multiplier_montant(a, b):
    return a * b


def _op_somme_montants(a, b):
    return a + b


# (fn, type_sortie, signature[types par position])
OPERATIONS: dict[str, tuple[Callable, str, tuple[type, ...]]] = {
    "ajouter_jours": (_op_ajouter_jours, "date", (date, int)),
    "soustraire_jours": (_op_soustraire_jours, "date", (date, int)),
    "difference_jours": (_op_difference_jours, "int", (date, date)),
    "multiplier_montant": (_op_multiplier_montant, "decimal", (Decimal, Decimal)),
    "somme_montants": (_op_somme_montants, "decimal", (Decimal, Decimal)),
}


class ResultatCalcul(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calcul_id: str
    valeur: str
    type: Literal["date", "decimal", "int"]


def _parse_litteral(arg: str) -> Valeur:
    try:
        return date.fromisoformat(arg)
    except ValueError:
        pass
    try:
        return int(arg)
    except ValueError:
        pass
    try:
        d = Decimal(arg)
    except Exception:
        raise ReferenceAbsente(f"argument introuvable : {arg!r}")
    if not d.is_finite():
        raise ReferenceAbsente(f"argument non-fini : {arg!r}")
    return d


def _coerce(val: Valeur, expected: type) -> Valeur:
    if isinstance(val, expected):
        return val
    if expected is Decimal and isinstance(val, int):
        return Decimal(val)
    raise TypeIncompatible(
        f"type {type(val).__name__} au lieu de {expected.__name__}"
    )


def _serialiser(v: Valeur) -> str:
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _deserialiser(rc: ResultatCalcul) -> Valeur:
    if rc.type == "date":
        return date.fromisoformat(rc.valeur)
    if rc.type == "decimal":
        return Decimal(rc.valeur)
    return int(rc.valeur)


def _verifier_inputs(inputs: dict[str, Valeur]) -> None:
    for nom, val in inputs.items():
        if isinstance(val, Decimal) and not val.is_finite():
            raise TypeIncompatible(
                f"input {nom!r} non-fini : {val!r}"
            )
        if isinstance(val, (date, int, Decimal)):
            continue
        raise TypeIncompatible(
            f"input {nom!r} de type {type(val).__name__} non supporte"
        )


def resoudre(
    calculs: list[Calcul],
    inputs: dict[str, Valeur] | None = None,
) -> dict[str, ResultatCalcul]:
    inputs = inputs or {}
    _verifier_inputs(inputs)
    par_id: dict[str, Calcul] = {}
    for c in calculs:
        if c.calcul_id in par_id:
            raise ReferenceAbsente(f"calcul_id duplique : {c.calcul_id}")
        par_id[c.calcul_id] = c

    cache: dict[str, ResultatCalcul] = {}
    stack: list[str] = []

    def resoudre_un(calcul_id: str) -> ResultatCalcul:
        if calcul_id in cache:
            return cache[calcul_id]
        if calcul_id in stack:
            cycle = stack[stack.index(calcul_id):] + [calcul_id]
            raise DependanceCirculaire(" -> ".join(cycle))
        if calcul_id not in par_id:
            raise ReferenceAbsente(f"calcul inconnu : {calcul_id}")
        calcul = par_id[calcul_id]
        if calcul.operation not in OPERATIONS:
            raise OperationInconnue(f"operation inconnue : {calcul.operation!r}")
        fn, type_sortie, signature = OPERATIONS[calcul.operation]
        if len(calcul.arguments) != len(signature):
            raise TypeIncompatible(
                f"{calcul.operation} attend {len(signature)} arguments, "
                f"recu {len(calcul.arguments)}"
            )

        stack.append(calcul_id)
        try:
            valeurs = []
            for i, (arg, expected) in enumerate(zip(calcul.arguments, signature)):
                if arg in par_id:
                    val = _deserialiser(resoudre_un(arg))
                elif arg in inputs:
                    val = inputs[arg]
                else:
                    val = _parse_litteral(arg)
                try:
                    val = _coerce(val, expected)
                except TypeIncompatible as exc:
                    raise TypeIncompatible(
                        f"{calcul_id}.arguments[{i}]: {exc}"
                    ) from exc
                valeurs.append(val)
            try:
                resultat_brut = fn(*valeurs)
            except OverflowError as exc:
                raise TypeIncompatible(
                    f"depassement arithmetique pour {calcul.operation}: {exc}"
                ) from exc
            except ArithmeticError as exc:
                raise TypeIncompatible(
                    f"erreur arithmetique pour {calcul.operation}: {exc}"
                ) from exc
        finally:
            stack.pop()

        if type_sortie == "date" and not isinstance(resultat_brut, date):
            raise TypeIncompatible(f"resultat non-date pour {calcul.operation}")
        if type_sortie == "decimal" and not isinstance(resultat_brut, Decimal):
            raise TypeIncompatible(f"resultat non-decimal pour {calcul.operation}")
        if type_sortie == "int" and not isinstance(resultat_brut, int):
            raise TypeIncompatible(f"resultat non-int pour {calcul.operation}")

        rc = ResultatCalcul(
            calcul_id=calcul_id,
            valeur=_serialiser(resultat_brut),
            type=type_sortie,
        )
        cache[calcul_id] = rc
        return rc

    return {c.calcul_id: resoudre_un(c.calcul_id) for c in calculs}
