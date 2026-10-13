"""Telecharge le corpus LEGI et construit la base SQLite de production.

Usage :
    PYTHONPATH=. python scripts/telecharger_corpus.py
    PYTHONPATH=. python scripts/telecharger_corpus.py --force
    PYTHONPATH=. python scripts/telecharger_corpus.py --tous-codes
    PYTHONPATH=. python scripts/telecharger_corpus.py --limite 1000
    PYTHONPATH=. python scripts/telecharger_corpus.py --base /tmp/test.sqlite

Idempotent : si la base cible existe deja, ne fait rien sauf avec --force.
Telecharge le dataset Hugging Face (~700 Mo) si absent du disque.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_huggingface_legi import SourceHuggingFaceLegi
from beaume.config import paths
from beaume.legal.model import CodeJuridique
from beaume.utils.logging import get_logger

log = get_logger("telecharger_corpus")

DATASET_HF_ID = "VinceGx33/legi-french-law-2025"

# Codes retenus par defaut (5 codes majeurs du contentieux courant).
CODES_DEFAUT: frozenset[CodeJuridique] = frozenset({
    CodeJuridique.CODE_CIVIL,
    CodeJuridique.CODE_TRAVAIL,
    CodeJuridique.CODE_SECURITE_SOCIALE,
    CodeJuridique.CODE_PROCEDURE_CIVILE,
    CodeJuridique.CODE_CONSOMMATION,
})


def _telecharger_dataset(chemin_dataset: Path) -> None:
    """Telecharge le dataset HF et le sauvegarde sur disque.

    Idempotent : ne fait rien si le dossier est deja rempli.
    """
    if chemin_dataset.is_dir() and any(chemin_dataset.iterdir()):
        log.info("Dataset deja present : %s", chemin_dataset)
        return

    try:
        from datasets import load_dataset
    except ImportError as e:
        raise SystemExit(
            "La lib 'datasets' est requise. "
            "Installe-la avec : pip install -e ."
        ) from e

    chemin_dataset.parent.mkdir(parents=True, exist_ok=True)
    log.info("Telechargement du dataset %s...", DATASET_HF_ID)
    log.info("Patience : ~700 Mo, plusieurs minutes selon la connexion.")

    ds = load_dataset(DATASET_HF_ID)
    ds.save_to_disk(str(chemin_dataset))
    log.info("Dataset sauvegarde : %s", chemin_dataset)


def _construire_base(
    chemin_dataset: Path,
    chemin_db: Path,
    codes: frozenset[CodeJuridique] | None,
    limite: int | None,
) -> int:
    """Charge les articles et les enregistre en SQLite.

    Retourne le nombre d'articles enregistres.
    """
    source = SourceHuggingFaceLegi(
        chemin_dataset=chemin_dataset,
        codes_inclus=set(codes) if codes else None,
        limite=limite,
    )
    articles = source.charger()
    if not articles:
        raise SystemExit("Aucun article charge — verifie le dataset.")

    chemin_db.parent.mkdir(parents=True, exist_ok=True)
    depot = DepotSQLite(chemin_db)
    depot.vider()
    depot.enregistrer(articles)
    return len(articles)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Telecharge le corpus LEGI et construit legi_full.sqlite.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reconstruit la base meme si elle existe deja.",
    )
    parser.add_argument(
        "--tous-codes",
        action="store_true",
        help="Inclut toules codes (par defaut : 5 codes majeurs).",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Limite le nombre d'articles (debug).",
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=None,
        help="Chemin de la base SQLite (defaut : data/vector/legi_full.sqlite).",
    )
    args = parser.parse_args()

    chemin_dataset = paths.LEGAL / "legi_2025"
    chemin_db = args.base if args.base else paths.VECTOR / "legi_full.sqlite"

    paths.ensure_dirs()

    if chemin_db.exists() and not args.force:
        taille_mo = chemin_db.stat().st_size / (1024 * 1024)
        print(f"Base deja presente : {chemin_db} ({taille_mo:.1f} Mo)")
        print("Rien a faire. Utilise --force pour reconstruire.")
        return 0

    codes: frozenset[CodeJuridique] | None = (
        None if args.tous_codes else CODES_DEFAUT
    )

    print(f"Dataset cible : {chemin_dataset}")
    print(f"Base cible    : {chemin_db}")
    print(f"Codes         : "
          f"{'tous' if codes is None else f'{len(codes)} codes'}")
    if args.limite:
        print(f"Limite        : {args.limite} articles")
    print()

    t0 = time.monotonic()

    _telecharger_dataset(chemin_dataset)
    log.info("Construction de la base SQLite...")
    n = _construire_base(chemin_dataset, chemin_db, codes, args.limite)

    duree = time.monotonic() - t0
    taille_mo = chemin_db.stat().st_size / (1024 * 1024)

    print()
    print("=== Rapport ===")
    print(f"Articles en base : {n}")
    print(f"Taille SQLite    : {taille_mo:.1f} Mo")
    print(f"Duree totale     : {duree:.1f} s")
    print(f"Base             : {chemin_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
