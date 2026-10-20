"""Reconstruit legi_full_v2.sqlite à partir du corpus DILA de Codex.

Lit `data/vector/legi_dila_v2/legi_dila.sqlite` (vue versions_articles),
filtre par code DILA (par défaut : 5 codes cibles), et écrit dans une
base `legi_full_v2.sqlite` compatible avec `DepotSQLite`.

Optimisations :
- Batch de 100 articles avant chaque `enregistrer()`, pour éviter un
  commit SQLite par article (chaque commit est un fsync).
- Checkpoint WAL tous les 1 000 articles (variable `CHECKPOINT_TOUS_LES_N`).

Refuse d'écraser une base existante sans `--force`.

Usage :
    PYTHONPATH=. .venv/bin/python scripts/reconstruire_corpus_dila.py
    PYTHONPATH=. .venv/bin/python scripts/reconstruire_corpus_dila.py --force
    PYTHONPATH=. .venv/bin/python scripts/reconstruire_corpus_dila.py \\
        --codes LEGITEXT000006072050,LEGITEXT000006070721
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_dila import SourceDila
from beaume.config import paths
from beaume.utils.logging import get_logger

log = get_logger("reconstruire_corpus_dila")


CHEMIN_SOURCE_DEFAUT = paths.VECTOR / "legi_dila_v2" / "legi_dila.sqlite"
CHEMIN_SORTIE_DEFAUT = paths.VECTOR / "legi_full_v2.sqlite"

# 5 codes cibles par défaut.
CODES_DEFAUT = (
    "LEGITEXT000006072050",  # Code du travail
    "LEGITEXT000006070721",  # Code civil
    "LEGITEXT000006073189",  # Code de la sécurité sociale
    "LEGITEXT000006069565",  # Code de la consommation
    "LEGITEXT000006070716",  # Code de procédure civile
)

# Nombre d'articles accumulés avant d'appeler depot.enregistrer().
# Un commit SQLite par article est trop lent (fsync par appel).
BATCH_ARTICLES = 100

# Checkpoint WAL tous les N articles (évite un WAL de plusieurs Go).
CHECKPOINT_TOUS_LES_N = 1000


def _parse_codes(brut: str | None) -> tuple[str, ...]:
    if brut is None:
        return CODES_DEFAUT
    codes = tuple(c.strip() for c in brut.split(",") if c.strip())
    if not codes:
        raise argparse.ArgumentTypeError("--codes ne peut pas être vide")
    return codes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=CHEMIN_SOURCE_DEFAUT,
        help=f"Base DILA à lire (défaut : {CHEMIN_SOURCE_DEFAUT})",
    )
    parser.add_argument(
        "--sortie", type=Path, default=CHEMIN_SORTIE_DEFAUT,
        help=f"Base à écrire (défaut : {CHEMIN_SORTIE_DEFAUT})",
    )
    parser.add_argument(
        "--codes", type=str, default=None,
        help="Codes DILA (LEGITEXT) séparés par virgule. Défaut : 5 codes cibles.",
    )
    parser.add_argument("--force", action="store_true", help="Écrase la sortie existante.")
    parser.add_argument(
        "--limite", type=int, default=None,
        help="Nombre maximum d'articles (None = tous).",
    )
    parser.add_argument(
        "--batch", type=int, default=BATCH_ARTICLES,
        help=f"Nombre d'articles par commit (défaut : {BATCH_ARTICLES}).",
    )
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error(f"Base DILA introuvable : {args.source}")
    if args.sortie.exists() and not args.force:
        parser.error(
            f"La sortie existe déjà : {args.sortie}. "
            "Utiliser --force pour écraser."
        )
    if args.batch <= 0:
        parser.error("--batch doit être > 0")

    codes = _parse_codes(args.codes)
    print(f"Source      : {args.source}")
    print(f"Sortie      : {args.sortie}")
    print(f"Codes DILA  : {len(codes)} code(s)")
    for c in codes:
        print(f"  - {c}")
    print(f"Batch       : {args.batch} articles/commit")
    print()

    with SourceDila(args.source, filtrer_conflits=True) as source:
        total_versions = source.compter(codes=codes)
        print(f"Versions à importer : {total_versions}")
        if total_versions == 0:
            print("Aucune version à importer. Vérifie les codes.", file=sys.stderr)
            return 1

        if args.sortie.exists():
            args.sortie.unlink()
        depot = DepotSQLite(args.sortie)

        n_articles = 0
        n_versions = 0
        statuts: Counter[str] = Counter()
        batch: list = []
        debut = datetime.now(timezone.utc)

        def _flush() -> None:
            nonlocal batch
            if batch:
                depot.enregistrer(batch)
                batch = []

        for article in source.iter_articles(codes=codes, limite=args.limite):
            batch.append(article)
            n_articles += 1
            n_versions += len(article.versions)
            for v in article.versions:
                statuts[v.statut.value] += 1

            if len(batch) >= args.batch:
                _flush()
                if n_articles % CHECKPOINT_TOUS_LES_N == 0:
                    depot._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

            if n_articles % 5000 == 0:
                duree = (datetime.now(timezone.utc) - debut).total_seconds()
                log.info(
                    "Progression : %d articles, %d versions (%.1f s)",
                    n_articles, n_versions, duree,
                )

        _flush()
        depot._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        duree = (datetime.now(timezone.utc) - debut).total_seconds()

    print()
    print("=== Résultat ===")
    print(f"Articles importés : {n_articles}")
    print(f"Versions importées : {n_versions}")
    print(f"Durée : {duree:.1f} s")
    print()
    print("=== Statuts ===")
    for statut, n in sorted(statuts.items()):
        print(f"  {statut}: {n}")
    print()
    print(f"Base écrite : {args.sortie}")
    print(f"Attribution : DILA — Légifrance, base LEGI, Licence Ouverte 2.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())