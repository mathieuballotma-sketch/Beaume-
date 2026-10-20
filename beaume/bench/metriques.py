"""Chargement des references et metriques de recherche reproductibles.

Les jeux `must_cite` sont des references positives, pas des jugements
exhaustifs de tous les articles pertinents. On mesure donc le rappel des
references connues et le taux de requetes qui en retrouvent une; on ne
presente pas une precision comme si toutes les non-references etaient
des exemples negatifs verifies.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from beaume.legal.normalisation import normaliser_numero

ReferenceArticle = tuple[str, str]


def cle_article(code: str, numero: str) -> ReferenceArticle:
    """Construit une cle stable code + numero normalise."""
    code_normalise = str(code).strip().lower()
    numero_normalise = normaliser_numero(str(numero))
    if not code_normalise or not numero_normalise:
        raise ValueError("code et numero d'article sont obligatoires")
    return code_normalise, numero_normalise


def charger_references_dossier(
    dossier: dict[str, Any],
    code_defaut: str | None = None,
) -> set[ReferenceArticle]:
    """Lit `must_cite`, en exigeant le code pour eviter les faux matchs."""
    valeurs = dossier.get("must_cite")
    if not isinstance(valeurs, list) or not valeurs:
        raise ValueError(
            f"Dossier {dossier.get('id', '<sans id>')} sans must_cite exploitable"
        )

    resultat: set[ReferenceArticle] = set()
    for valeur in valeurs:
        if isinstance(valeur, dict):
            code = valeur.get("code") or dossier.get("code") or code_defaut
            numero = valeur.get("numero")
        else:
            code = dossier.get("code") or code_defaut
            numero = valeur
        if not code:
            raise ValueError(
                f"Code absent pour une reference de {dossier.get('id', '<sans id>')}"
            )
        if not numero:
            raise ValueError(
                f"Numero absent pour une reference de {dossier.get('id', '<sans id>')}"
            )
        resultat.add(cle_article(str(code), str(numero)))
    return resultat


def calculer_rappel(
    references: Sequence[set[ReferenceArticle]],
    classements: Sequence[Sequence[ReferenceArticle]],
    k_values: Sequence[int] = (1, 5, 10),
) -> dict[str, Any]:
    """Calcule Recall@K, macro-recall, hit-rate@K et MRR.

    Les classements sont dedoublonnes en conservant la premiere position.
    Les ensembles de references doivent etre positifs et non vides.
    """
    if len(references) != len(classements):
        raise ValueError("references et classements doivent avoir la meme taille")
    if not references:
        raise ValueError("au moins une requete est necessaire")
    ks = tuple(sorted(set(k_values)))
    if not ks or any(k <= 0 for k in ks):
        raise ValueError("k_values doit contenir des entiers strictement positifs")
    if any(not r for r in references):
        raise ValueError("chaque requete doit avoir au moins une reference positive")

    classements_uniques: list[list[ReferenceArticle]] = []
    for classement in classements:
        vus: set[ReferenceArticle] = set()
        uniques: list[ReferenceArticle] = []
        for item in classement:
            if item not in vus:
                vus.add(item)
                uniques.append(item)
        classements_uniques.append(uniques)

    total_references = sum(len(r) for r in references)
    mrr_total = 0.0
    for reference, classement in zip(references, classements_uniques):
        rangs = [i for i, item in enumerate(classement, start=1) if item in reference]
        if rangs:
            mrr_total += 1.0 / min(rangs)

    par_k: dict[str, dict[str, float | int]] = {}
    for k in ks:
        hits_par_requete = [
            len(reference.intersection(classement[:k]))
            for reference, classement in zip(references, classements_uniques)
        ]
        hits = sum(hits_par_requete)
        par_k[str(k)] = {
            "references_retrouvees": hits,
            "rappel_micro": hits / total_references,
            "rappel_macro": sum(
                h / len(reference)
                for h, reference in zip(hits_par_requete, references)
            ) / len(references),
            "taux_requetes_avec_au_moins_un_hit": sum(
                h > 0 for h in hits_par_requete
            ) / len(references),
        }

    return {
        "n_requetes": len(references),
        "n_references": total_references,
        "mrr": mrr_total / len(references),
        "par_k": par_k,
    }
