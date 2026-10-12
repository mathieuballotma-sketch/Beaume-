"""Charge le corpus initial dans la base SQLite.

Lit data/legal/corpus_initial.json, l'enregistre dans data/vector/legi.sqlite
et affiche un rapport.

Usage :
    PYTHONPATH=. python scripts/charger_corpus.py
"""
from pathlib import Path

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.config import paths
from beaume.utils.profiler import profil_actif


def main() -> int:
    source_json = paths.LEGAL / "corpus_initial.json"
    chemin_db = paths.VECTOR / "legi.sqlite"

    if not source_json.exists():
        print(f"Fichier introuvable : {source_json}")
        return 1

    print(f"Source    : {source_json}")
    print(f"Base      : {chemin_db}")

    source = SourceFichierLocal(source_json)
    depot = DepotSQLite(chemin_db)

    with profil_actif("chargement") as p:
        articles = source.charger()
        depot.enregistrer(articles)

    print()
    print(f"Articles charges : {len(articles)}")
    print(f"Articles en base : {depot.compter()}")
    print()
    print(p.rapport())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
