"""Analyse un dossier client et produit un rapport Markdown.

Usage :
    PYTHONPATH=. python scripts/analyser_dossier.py <dossier> [date]
    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_001 2024-01-01
    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_001

Base de production : data/vector/legi_full.sqlite (25 767 articles).
Si absente, le script refuse de tourner et indique quoi faire.

Mode demo (tests rapides, 5 articles) :
    BEAUME_CORPUS_DEMO=1 python scripts/analyser_dossier.py <dossier>
"""
import os
import sys
from datetime import date
from pathlib import Path

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.generateur_ollama import (
    SCHEMA_ANALYSE,
    GenerateurOllama,
)
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.config import paths
from beaume.ports.registre import RegistreExtracteurs
from beaume.utils.logging import get_logger
from beaume.utils.profiler import profil_actif

log = get_logger("analyser_dossier")

_VAR_DEMO = "BEAUME_CORPUS_DEMO"


def _construire_registre() -> RegistreExtracteurs:
    r = RegistreExtracteurs()
    r.enregistrer(ExtracteurPDF())
    return r


def _construire_depot() -> DepotSQLite:
    """Ouvre la base SQLite du corpus.

    Par defaut : base de production legi_full.sqlite (25 767 articles).
    Si absente : erreur fatale (jamais de rapport vide silencieux).

    Mode demo (BEAUME_CORPUS_DEMO=1) : utilise legi.sqlite construit
    depuis corpus_initial.json. Rapide (5 articles), pour les tests.
    """
    if os.environ.get(_VAR_DEMO) == "1":
        return _construire_depot_demo()

    chemin_db = paths.VECTOR / "legi_full.sqlite"
    if not chemin_db.exists():
        raise SystemExit(
            f"Corpus complet absent : {chemin_db}\n"
            "\n"
            "Deux options :\n"
            "  1. Construire le corpus (recommande) :\n"
            "       PYTHONPATH=. python scripts/telecharger_corpus.py\n"
            "  2. Utiliser le petit corpus de demo (5 articles) :\n"
            f"       {_VAR_DEMO}=1 python scripts/analyser_dossier.py <dossier>\n"
        )

    depot = DepotSQLite(chemin_db)
    log.info("Corpus PRODUCTION : %d articles", depot.compter())
    return depot


def _construire_depot_demo() -> DepotSQLite:
    """Base demo construite depuis corpus_initial.json (5 articles)."""
    source_json = paths.LEGAL / "corpus_initial.json"
    if not source_json.exists():
        raise SystemExit(
            f"Corpus demo introuvable : {source_json}\n"
            f"Desactive {_VAR_DEMO} ou restaure le fichier."
        )

    chemin_db = paths.VECTOR / "legi.sqlite"
    depot = DepotSQLite(chemin_db)
    depot.vider()
    depot.enregistrer(SourceFichierLocal(source_json).charger())
    log.info("Corpus DEMO : %d articles", depot.compter())
    return depot


def main(dossier: str, date_str: str | None) -> int:
    dossier_path = Path(dossier).expanduser().resolve()
    if not dossier_path.exists():
        log.error("Dossier introuvable")
        return 1

    date_ref = (
        date.fromisoformat(date_str) if date_str else date.today()
    )

    log.info("Analyse locale demarree (date de reference=%s)", date_ref)

    depot = _construire_depot()
    registre = _construire_registre()
    chercheur = ChercheurArticlesFTS5(depot)
    generateur = GenerateurOllama(schema=SCHEMA_ANALYSE)
    verificateur = VerificateurStandard(depot)

    pipeline = PipelineAnalyse(
        registre=registre,
        chercheur=chercheur,
        generateur=generateur,
        depot=depot,
        verificateur=verificateur,
    )

    nom_dossier = dossier_path.name
    chemin_sortie = paths.OUT / f"{nom_dossier}_analyse.md"

    with profil_actif("analyse") as profil:
        rapport, _ = pipeline.executer(
            dossier_path, date_ref, chemin_sortie=chemin_sortie,
        )

    print()
    print(f"Dossier         : {nom_dossier}")
    print(f"Date reference  : {date_ref}")
    print(f"Citations       : {len(rapport.verifications)} "
          f"({len(rapport.citations_valides)} valides, "
          f"{len(rapport.citations_rejetees)} rejetees)")
    print(f"Duree           : {rapport.duree_s:.2f} s")
    print(f"Rapport ecrit   : {chemin_sortie.name}")
    print()
    print(profil.rapport())
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python scripts/analyser_dossier.py <dossier> [date ISO]")
        sys.exit(2)
    dossier = sys.argv[1]
    date_arg = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(main(dossier, date_arg))
