"""Benchmark de la recherche d'articles.

Genere N requetes automatiquement a partir du corpus lui-meme
(self-retrieval), interroge le chercheur, mesure le rappel.

Usage :
    PYTHONPATH=. python scripts/bench_recherche.py --n 1000
"""
import argparse
import json
import random
import time
from datetime import date
from pathlib import Path

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.config import paths
from beaume.utils.texte import extraire_mots_cles


CHEMIN_DB = paths.VECTOR / "legi_full.sqlite"
CHEMIN_RESULTAT = paths.TMP / "bench_recherche.json"


def _construire_requete(depot: DepotSQLite, article_id: str) -> str | None:
    """Construit une requete a partir du texte d'un article."""
    # On lit le texte de l'article depuis la base
    ligne = depot._conn.execute(
        "SELECT texte FROM versions WHERE article_id = ? LIMIT 1",
        (article_id,),
    ).fetchone()
    if ligne is None:
        return None
    texte = ligne["texte"]
    # On extrait 10 mots-cles
    mots = extraire_mots_cles(texte, limite=10)
    if not mots:
        return None
    return " ".join(mots)


def _lister_article_ids(depot: DepotSQLite, n: int) -> list[tuple[str, str]]:
    """Retourne N (article_id, code) aleatoires."""
    lignes = depot._conn.execute(
        "SELECT id, code FROM articles ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    return [(l["id"], l["code"]) for l in lignes]


def main(n: int, graine: int) -> int:
    if not CHEMIN_DB.exists():
        print(f"Base introuvable : {CHEMIN_DB}")
        return 1

    random.seed(graine)

    depot = DepotSQLite(CHEMIN_DB)
    chercheur = ChercheurArticlesFTS5(depot)

    total = depot.compter()
    print(f"Corpus : {total} articles")
    print(f"Tests  : {n} requetes aleatoires")
    print()

    # On tire N articles
    echantillon = _lister_article_ids(depot, n)
    print(f"Echantillon : {len(echantillon)} articles")
    print()

    resultats = {
        "n_total": n,
        "rappel_1": 0,
        "rappel_5": 0,
        "rappel_10": 0,
        "temps_ms_total": 0.0,
        "echecs": [],
        "succes": [],
    }

    debut = time.perf_counter()
    for i, (article_id, code) in enumerate(echantillon):
        requete = _construire_requete(depot, article_id)
        if requete is None:
            continue

        t0 = time.perf_counter()
        hits = chercheur.chercher(requete, limite=10)
        t1 = time.perf_counter()
        resultats["temps_ms_total"] += (t1 - t0) * 1000

        ids_trouves = [h.article_id for h in hits]

        dans_1 = article_id in ids_trouves[:1]
        dans_5 = article_id in ids_trouves[:5]
        dans_10 = article_id in ids_trouves[:10]

        if dans_1:
            resultats["rappel_1"] += 1
        if dans_5:
            resultats["rappel_5"] += 1
        if dans_10:
            resultats["rappel_10"] += 1

        entree = {
            "article_id": article_id,
            "code": code,
            "requete": requete[:80],
            "top_1": ids_trouves[0] if ids_trouves else None,
            "dans_top_1": dans_1,
            "dans_top_5": dans_5,
            "dans_top_10": dans_10,
        }
        if dans_5:
            resultats["succes"].append(entree)
        else:
            resultats["echecs"].append(entree)

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{n}...")

    duree = time.perf_counter() - debut

    print()
    print("=== Resultats ===")
    print(f"Tests effectifs  : {len(resultats['succes']) + len(resultats['echecs'])}")
    print(f"Rappel@1         : {resultats['rappel_1'] / n * 100:.1f} %")
    print(f"Rappel@5         : {resultats['rappel_5'] / n * 100:.1f} %")
    print(f"Rappel@10        : {resultats['rappel_10'] / n * 100:.1f} %")
    print(f"Temps moyen      : {resultats['temps_ms_total'] / n:.1f} ms")
    print(f"Duree totale     : {duree:.1f} s")
    print()

    CHEMIN_RESULTAT.parent.mkdir(parents=True, exist_ok=True)
    CHEMIN_RESULTAT.write_text(
        json.dumps(resultats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Resultats ecrits : {CHEMIN_RESULTAT}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--graine", type=int, default=42)
    args = parser.parse_args()
    raise SystemExit(main(args.n, args.graine))