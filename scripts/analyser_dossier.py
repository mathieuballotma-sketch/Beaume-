"""Analyse un dossier client et produit un rapport Markdown.

Usage :
    PYTHONPATH=. python scripts/analyser_dossier.py <dossier> [date]
    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_001 2024-01-01
    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_001

Le script :
1. Charge le corpus legal dans SQLite.
2. Construit le pipeline complet (analyse + verification).
3. Produit out/<nom_dossier>_analyse.md.
"""
import sys
from datetime import date
from pathlib import Path

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.generateur_ollama import GenerateurOllama
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.config import paths
from beaume.ports.registre import RegistreExtracteurs
from beaume.utils.logging import get_logger
from beaume.utils.profiler import profil_actif

log = get_logger("analyser_dossier")


def _construire_registre() -> RegistreExtracteurs:
    r = RegistreExtracteurs()
    r.enregistrer(ExtracteurPDF())
    return r


def _construire_depot() -> DepotSQLite:
    chemin_db = paths.VECTOR / "legi.sqlite"
    depot = DepotSQLite(chemin_db)

    source_json = paths.LEGAL / "corpus_initial.json"
    if source_json.exists():
        depot.vider()
        depot.enregistrer(SourceFichierLocal(source_json).charger())
        log.info("Corpus charge : %d articles", depot.compter())
    else:
        log.warning("Corpus absent : %s", source_json)

    return depot


def main(dossier: str, date_str: str | None) -> int:
    dossier_path = Path(dossier).expanduser().resolve()
    if not dossier_path.exists():
        log.error("Dossier introuvable : %s", dossier_path)
        return 1

    date_ref = (
        date.fromisoformat(date_str) if date_str else date.today()
    )

    log.info("Analyse : %s au %s", dossier_path, date_ref)

    depot = _construire_depot()
    registre = _construire_registre()
    chercheur = ChercheurArticlesFTS5(depot)
    generateur = GenerateurOllama()
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
    print(f"Dossier         : {dossier_path}")
    print(f"Date reference  : {date_ref}")
    print(f"Citations       : {len(rapport.verifications)} "
          f"({len(rapport.citations_valides)} valides, "
          f"{len(rapport.citations_rejetees)} rejetees)")
    print(f"Duree           : {rapport.duree_s:.2f} s")
    print(f"Rapport ecrit   : {chemin_sortie}")
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
