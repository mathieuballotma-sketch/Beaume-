"""Benchmark de retrieval d'articles.

Mode par defaut : requetes factuelles annotees dans `dossiers_test.json`.
Le mode `self_retrieval` est conserve uniquement comme diagnostic d'index;
il ne mesure pas la pertinence d'articles a partir de faits clients.

Exemples :
    PYTHONPATH=. python scripts/bench_recherche.py
    PYTHONPATH=. python scripts/bench_recherche.py --mode self_retrieval --n 1000
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.bench.metriques import (
    ReferenceArticle,
    calculer_rappel,
    charger_references_dossier,
    cle_article,
)
from beaume.config import paths
from beaume.utils.texte import extraire_mots_cles


CHEMIN_DB = paths.VECTOR / "legi_full.sqlite"
FICHIER_DEFAUT = Path(__file__).resolve().parents[1] / "beaume" / "bench" / "dossiers_test.json"


def _charger_donnees(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with path.open(encoding="utf-8") as fichier:
        data = json.load(fichier)
    if not isinstance(data, dict) or not isinstance(data.get("dossiers"), list):
        raise ValueError("Le benchmark doit contenir une liste 'dossiers'.")
    meta = data.get("_meta", {})
    if not isinstance(meta, dict):
        raise ValueError("La metadonnee '_meta' doit etre un objet.")
    dossiers = data["dossiers"]
    if not dossiers:
        raise ValueError("Le benchmark ne contient aucun dossier.")
    for index, dossier in enumerate(dossiers, start=1):
        if not isinstance(dossier, dict) or not dossier.get("texte"):
            raise ValueError("Chaque dossier doit avoir un identifiant et un texte.")
        dossier.setdefault("id", f"requete-{index:03d}")
        charger_references_dossier(dossier, meta.get("code"))
    return meta, dossiers


def _construire_requete_auto(depot: DepotSQLite, article_id: str) -> str | None:
    ligne = depot._conn.execute(
        "SELECT texte FROM versions WHERE article_id = ? ORDER BY date_debut DESC LIMIT 1",
        (article_id,),
    ).fetchone()
    if ligne is None:
        return None
    mots = extraire_mots_cles(ligne["texte"], limite=10)
    return " ".join(mots) if mots else None


def _echantillon_auto(
    depot: DepotSQLite, n: int, graine: int,
) -> list[tuple[str, str, str]]:
    if n <= 0:
        raise ValueError("n doit etre strictement positif")
    lignes = depot._conn.execute(
        "SELECT id, code, numero FROM articles ORDER BY id"
    ).fetchall()
    echantillon = random.Random(graine).sample(lignes, min(n, len(lignes)))
    return [(l["id"], l["code"], l["numero"]) for l in echantillon]


def _classer(
    chercheur: ChercheurArticlesFTS5,
    texte: str,
    limite: int,
) -> list[ReferenceArticle]:
    hits = chercheur.chercher(texte, limite=limite)
    classement: list[ReferenceArticle] = []
    for hit in hits:
        classement.append(cle_article(hit.code, hit.numero))
    return classement


def _executer_annote(
    depot: DepotSQLite,
    chercheur: ChercheurArticlesFTS5,
    dossiers: list[dict[str, Any]],
    code_defaut: str | None,
    k_max: int,
) -> tuple[list[set[ReferenceArticle]], list[list[ReferenceArticle]], list[dict[str, Any]]]:
    references: list[set[ReferenceArticle]] = []
    classements: list[list[ReferenceArticle]] = []
    details: list[dict[str, Any]] = []
    for dossier in dossiers:
        gold = charger_references_dossier(dossier, code_defaut)
        ranking = _classer(chercheur, dossier["texte"], k_max)
        trouve = [ref for ref in ranking if ref in gold]
        references.append(gold)
        classements.append(ranking)
        details.append({
            "id": dossier["id"],
            "n_references": len(gold),
            "references": [list(x) for x in sorted(gold)],
            "classement": [list(x) for x in ranking],
            "references_trouvees": [list(x) for x in trouve],
        })
    return references, classements, details


def _executer_self_retrieval(
    depot: DepotSQLite,
    chercheur: ChercheurArticlesFTS5,
    n: int,
    graine: int,
    k_max: int,
) -> tuple[list[set[ReferenceArticle]], list[list[ReferenceArticle]], list[dict[str, Any]]]:
    echantillon = _echantillon_auto(depot, n, graine)
    references: list[set[ReferenceArticle]] = []
    classements: list[list[ReferenceArticle]] = []
    details: list[dict[str, Any]] = []
    for article_id, code, numero in echantillon:
        requete = _construire_requete_auto(depot, article_id)
        if not requete:
            continue
        gold = {cle_article(code, numero)}
        ranking = _classer(chercheur, requete, k_max)
        references.append(gold)
        classements.append(ranking)
        details.append({
            "article_id": article_id,
            "reference": [code, numero],
            "classement": [list(x) for x in ranking],
        })
    if not references:
        raise RuntimeError("Aucune requete exploitable dans le mode self_retrieval.")
    return references, classements, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("faits_annotees", "self_retrieval"),
        default="faits_annotees",
        help="self_retrieval est un diagnostic d'index, pas une validation juridique.",
    )
    parser.add_argument("--fichier", type=Path, default=FICHIER_DEFAUT)
    parser.add_argument("--base", type=Path, default=CHEMIN_DB)
    parser.add_argument("--n", type=int, default=1000, help="Requetes en mode self_retrieval.")
    parser.add_argument("--graine", type=int, default=42)
    parser.add_argument("--k", type=int, nargs="+", default=[1, 5, 10])
    parser.add_argument("--sortie", type=Path, default=None)
    args = parser.parse_args()

    if not args.base.is_file():
        parser.error(f"Base introuvable : {args.base}")
    if any(k <= 0 for k in args.k):
        parser.error("Toutes les valeurs de --k doivent etre positives.")

    depot = DepotSQLite(args.base, lecture_seule=True)
    chercheur = ChercheurArticlesFTS5(depot)
    t0 = time.perf_counter()
    metadata: dict[str, Any] = {}
    if args.mode == "faits_annotees":
        if not args.fichier.is_file():
            parser.error(f"Jeu de requetes introuvable : {args.fichier}")
        metadata, dossiers = _charger_donnees(args.fichier)
        references, classements, details = _executer_annote(
            depot, chercheur, dossiers, metadata.get("code"), max(args.k),
        )
        validation_labels = metadata.get(
            "statut_annotations", "non_documente",
        )
        sortie_defaut = paths.TMP / "bench_recherche_annote.json"
    else:
        references, classements, details = _executer_self_retrieval(
            depot, chercheur, args.n, args.graine, max(args.k),
        )
        validation_labels = "self_retrieval_diagnostic_non_juridique"
        sortie_defaut = paths.TMP / "bench_recherche_self_retrieval_diagnostic.json"

    metriques = calculer_rappel(references, classements, args.k)
    duree_s = time.perf_counter() - t0
    resultat = {
        "type_evaluation": args.mode,
        "jeu": str(args.fichier) if args.mode == "faits_annotees" else None,
        "statut_annotations": validation_labels,
        "methode": "FTS5 OR + BM25",
        "base": str(args.base),
        "n_articles_corpus": depot.compter(),
        "graine": args.graine if args.mode == "self_retrieval" else None,
        "duree_s": duree_s,
        "metriques": metriques,
        "details": details,
        "interpretation": (
            "Le self-retrieval utilise le texte de l'article cible comme requete; "
            "il mesure le comportement de l'index, pas la pertinence faits-vers-lois."
            if args.mode == "self_retrieval" else
            "Les references must_cite sont positives non exhaustives; aucun score de precision n'est calcule."
        ),
    }

    sortie = args.sortie or sortie_defaut
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Mode             : {args.mode}")
    print(f"Requetes         : {metriques['n_requetes']}")
    print(f"References       : {metriques['n_references']}")
    print(f"MRR              : {metriques['mrr']:.3f}")
    for k, valeurs in metriques["par_k"].items():
        print(
            f"Recall@{k:<2}        : {valeurs['rappel_micro']:.1%} "
            f"(macro {valeurs['rappel_macro']:.1%}; "
            f"hit-rate {valeurs['taux_requetes_avec_au_moins_un_hit']:.1%})"
        )
    print(f"Annotations      : {validation_labels}")
    print(f"Rapport          : {sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
