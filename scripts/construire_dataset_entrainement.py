"""Construit le dataset d'entrainement pour le modele d'embedding.

Entree  : un fichier faits_clients (JSONL, une paire par ligne)
Sorties : data/training/dataset_entrainement.parquet
          data/training/dataset_entrainement_manifest.json

Colonnes du parquet : anchor, positive, article, id_fait, date_fait.

Le manifeste trace : fichier source, date de generation, nombre de
paires, articles manquants. Il permet de savoir sur quoi on a
entraine.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from beaume.config import paths
from beaume.legal.normalisation import normaliser_numero

CHEMIN_FAITS_DEFAUT = paths.DATA / "training" / "faits_clients_propres.jsonl"
CHEMIN_SORTIE = paths.DATA / "training" / "dataset_entrainement.parquet"
CHEMIN_MANIFESTE = paths.DATA / "training" / "dataset_entrainement_manifest.json"
CHEMIN_DB = paths.VECTOR / "legi_full.sqlite"
TAILLE_MAX_ARTICLE = 2000


def _charger_articles(conn: sqlite3.Connection) -> dict[str, str]:
    """Charge tous les articles en memoire.

    Note : la cle est le numero seul. Deux codes differents avec le
    meme numero (ex: L1234-1 du Code du travail et L1234-1 du Code
    de la consommation) se ecrasent. Limite connue, a corriger
    quand on aura le code juridique dans les faits_clients.
    """
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
    chemin_faits: Path,
    articles: dict[str, str],
    max_par_fait: int,
) -> tuple[list[dict], dict]:
    """Construit la liste des paires (anchor, positive)."""
    paires: list[dict] = []
    n_faits = 0
    n_manquants = 0
    n_lignes_ignorees = 0
    articles_manquants: list[str] = []

    with chemin_faits.open(encoding="utf-8") as f_in:
        for ligne in f_in:
            try:
                d = json.loads(ligne)
            except json.JSONDecodeError:
                n_lignes_ignorees += 1
                continue

            faits = d.get("faits_client", "").strip()
            articles_cites = d.get("articles", [])
            id_fait = d.get("id", "")
            date_fait = d.get("date", "")

            if not faits or not articles_cites or not id_fait:
                n_lignes_ignorees += 1
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
                    articles_manquants.append(num)
                    continue

                paires.append({
                    "anchor": faits,
                    "positive": texte[:TAILLE_MAX_ARTICLE],
                    "article": num,
                    "id_fait": id_fait,
                    "date_fait": date_fait,
                })
                n_ecrits += 1

    stats = {
        "n_faits": n_faits,
        "n_paires": len(paires),
        "n_manquants": n_manquants,
        "n_lignes_ignorees": n_lignes_ignorees,
        "articles_manquants_uniques": sorted(set(articles_manquants)),
    }
    return paires, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--faits",
        type=Path,
        default=CHEMIN_FAITS_DEFAUT,
        help="Fichier JSONL de faits clients.",
    )
    parser.add_argument("--max-par-fait", type=int, default=3)
    args = parser.parse_args()

    if not args.faits.exists():
        raise SystemExit(f"Introuvable : {args.faits}")
    if not CHEMIN_DB.exists():
        raise SystemExit(f"Introuvable : {CHEMIN_DB}")

    conn = sqlite3.connect(str(CHEMIN_DB))
    conn.row_factory = sqlite3.Row
    try:
        articles = _charger_articles(conn)
    finally:
        conn.close()

    CHEMIN_SORTIE.parent.mkdir(parents=True, exist_ok=True)

    paires, stats = _construire_paires(
        args.faits, articles, args.max_par_fait,
    )

    if not paires:
        raise SystemExit("Aucune paire generee. Verifie le fichier source.")

    df = pd.DataFrame(paires)
    df.to_parquet(CHEMIN_SORTIE, index=False)

    manifeste = {
        "genere_le": datetime.now(timezone.utc).isoformat(),
        "fichier_source": str(args.faits),
        "fichier_source_sha256": _sha256(args.faits),
        "fichier_sortie": str(CHEMIN_SORTIE),
        "max_par_fait": args.max_par_fait,
        "db_articles": str(CHEMIN_DB),
        **stats,
    }
    CHEMIN_MANIFESTE.write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== Resultats ===")
    print(f"Fichier source      : {args.faits}")
    print(f"Faits traites       : {stats['n_faits']}")
    print(f"Paires generees     : {stats['n_paires']}")
    print(f"Articles manquants  : {stats['n_manquants']}")
    print(f"Lignes ignorees     : {stats['n_lignes_ignorees']}")
    print(f"Faits distincts     : {df['id_fait'].nunique()}")
    print(f"Sortie              : {CHEMIN_SORTIE}")
    print(f"Manifeste           : {CHEMIN_MANIFESTE}")
    return 0


def _sha256(chemin: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())