"""Audite le dataset Hugging Face LEGI local.

Repond a :
- Combien de lignes au total ?
- Quels champs sont exposes ?
- Quels etats (VIGUEUR, ABROGE, ...) sont presents ?
- Combien d'articles distincts vs versions totales ?
- Combien de versions par article ?
- Quelle est la plage temporelle couverte ?
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from beaume.config import paths

CHEMIN_DATASET = paths.LEGAL / "legi_2025"


def main() -> int:
    if not CHEMIN_DATASET.exists():
        raise SystemExit(
            f"Introuvable : {CHEMIN_DATASET}\n"
            "Verifie le chemin dans scripts/telecharger_corpus.py."
        )

    from datasets import load_from_disk

    print(f"Chargement {CHEMIN_DATASET}...")
    ds = load_from_disk(str(CHEMIN_DATASET))
    train = ds["train"]

    print(f"Lignes totales : {len(train)}")
    print(f"Colonnes       : {list(train.column_names)}")
    print()

    # Echantillon pour ne pas tout scanner en memoire
    n_scan = min(len(train), 500_000)
    print(f"Scan de {n_scan} lignes pour analyse...")

    etats: Counter = Counter()
    articles_distincts: set[str] = set()
    versions_par_article: Counter = Counter()
    dates_debut: list[str] = []
    dates_fin: list[str] = []

    for i, row in enumerate(train):
        if i >= n_scan:
            break

        etat = row.get("article_etat", "INCONNU")
        etats[etat] += 1

        art_id = row.get("article_id", "")
        if art_id:
            articles_distincts.add(art_id)
            versions_par_article[art_id] += 1

        dd = row.get("date_debut")
        df = row.get("date_fin")
        if dd:
            dates_debut.append(str(dd))
        if df:
            dates_fin.append(str(df))

    print()
    print("=== Etats ===")
    for etat, n in etats.most_common():
        print(f"  {etat:20s} : {n}")

    print()
    print("=== Articles ===")
    print(f"Articles distincts : {len(articles_distincts)}")
    print(f"Lignes scannees    : {n_scan}")
    if articles_distincts:
        ratio = n_scan / len(articles_distincts)
        print(f"Ratio versions/article : {ratio:.2f}")

    print()
    print("=== Distribution versions/article (top 10) ===")
    for art_id, n in versions_par_article.most_common(10):
        print(f"  {art_id:50s} : {n} version(s)")

    print()
    print("=== Plage temporelle ===")
    if dates_debut:
        print(f"date_debut min : {min(dates_debut)}")
        print(f"date_debut max : {max(dates_debut)}")
    if dates_fin:
        print(f"date_fin min   : {min(dates_fin)}")
        print(f"date_fin max   : {max(dates_fin)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())