"""Construit le dataset d'entrainement pour le modele d'embedding.

Sortie : data/training/dataset_entrainement.parquet
Colonnes : anchor, positive, article, id_fait, date_fait
"""
from __future__ import annotations

import argparse
import json
import sqlite3

import pandas as pd

from beaume.config import paths
from beaume.legal.normalisation import normaliser_numero

CHEMIN_FAITS = paths.DATA / "training" / "faits_clients_2.jsonl"
CHEMIN_SORTIE = paths.DATA / "training" / "dataset_entrainement.parquet"
CHEMIN_DB = paths.VECTOR / "legi_full.sqlite"
TAILLE_MAX_ARTICLE = 2000


def _charger_articles(conn: sqlite3.Connection) -> dict[str, str]:
    print("Chargement des articles en memoire...")
    articles: dict[str, str] = {}
    for ligne in conn.execute("""
        SELECT a.numero AS numero, v.texte AS texte
        FROM articles a
        JOIN versions v ON v.article_id = a.id
    """):
        num = ligne["numero"]
        if num not in articles:
            articles[num] = ligne["texte"]
    print(f"  {len(articles)} articles charges.")
    return articles


def _construire_paires(
    chemin_faits,
    articles: dict[str, str],
    max_par_fait: int,
) -> tuple[list[dict], int, int]:
    paires: list[dict] = []
    n_faits = 0
    n_manquants = 0

    with chemin_faits.open(encoding="utf-8") as f_in:
        for ligne in f_in:
            d = json.loads(ligne)
            faits = d.get("faits_client", "").strip()
            articles_cites = d.get("articles", [])
            id_fait = d.get("id", "")
            date_fait = d.get("date", "")
            if not faits or not articles_cites or not id_fait:
                continue

            n_faits += 1
            n_ecrits = 0
            for num in articles_cites:
                if n_ecrits >= max_par_fait:
                    break
                try:
                    num_norm = normaliser_numero(num)
                except Exception:
                    num_norm = num

                texte = articles.get(num_norm) or articles.get(num)
                if texte is None:
                    n_manquants += 1
                    continue

                paires.append({
                    "anchor": faits,
                    "positive": texte[:TAILLE_MAX_ARTICLE],
                    "article": num,
                    "id_fait": id_fait,
                    "date_fait": date_fait,
                })
                n_ecrits += 1

    return paires, n_faits, n_manquants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-par-fait", type=int, default=3)
    args = parser.parse_args()

    if not CHEMIN_FAITS.exists():
        raise SystemExit(f"Introuvable : {CHEMIN_FAITS}")
    if not CHEMIN_DB.exists():
        raise SystemExit(f"Introuvable : {CHEMIN_DB}")

    conn = sqlite3.connect(str(CHEMIN_DB))
    conn.row_factory = sqlite3.Row
    articles = _charger_articles(conn)
    conn.close()

    CHEMIN_SORTIE.parent.mkdir(parents=True, exist_ok=True)

    paires, n_faits, n_manquants = _construire_paires(
        CHEMIN_FAITS, articles, args.max_par_fait
    )

    df = pd.DataFrame(paires)
    df.to_parquet(CHEMIN_SORTIE, index=False)

    print()
    print("=== Resultats ===")
    print(f"Faits traites       : {n_faits}")
    print(f"Paires generees     : {len(df)}")
    print(f"Articles manquants  : {n_manquants}")
    print(f"Faits distincts     : {df['id_fait'].nunique()}")
    print(f"Sortie              : {CHEMIN_SORTIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())