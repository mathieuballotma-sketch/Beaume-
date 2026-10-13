"""Benchmark de qualite : mesure la fiabilite de Beaume sur des dossiers.

Pour chaque dossier du jeu de test :
  1. Convertit le texte en PDF temporaire.
  2. Lance le pipeline complet (analyse + verification).
  3. Compare les citations VALIDES aux articles attendus (must_cite).
  4. Un dossier est REUSSI si AU MOINS UN article attendu figure parmi
     les citations valides.

Sortie : rapport texte + fichier JSON dans data/tmp/.

Usage :
    PYTHONPATH=. python scripts/bench_qualite.py
    PYTHONPATH=. python scripts/bench_qualite.py --fichier beaume/bench/dossiers_test.json
"""
import argparse
import json
import shutil
import tempfile
import time
from datetime import date
from pathlib import Path

import pymupdf

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.generateur_ollama import GenerateurOllama
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.config import paths
from beaume.legal.normalisation import normaliser_numero
from beaume.ports.registre import RegistreExtracteurs
from beaume.utils.logging import get_logger

log = get_logger("bench_qualite")

_CHEMIN_DEFAUT = Path(__file__).parent.parent / "beaume" / "bench" / "dossiers_test.json"


def _charger_dossiers(chemin: Path) -> list[dict]:
    with chemin.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["dossiers"]


def _creer_pdf(texte: str, chemin: Path) -> None:
    """Convertit un texte en PDF d'une page."""
    doc = pymupdf.open()
    page = doc.new_page()
    # On ecrit le texte dans une zone large, avec wrap manuel
    rect = pymupdf.Rect(50, 50, 545, 780)
    page.insert_textbox(rect, texte, fontsize=11)
    doc.save(str(chemin))
    doc.close()


def _construire_pipeline(depot: DepotSQLite) -> PipelineAnalyse:
    registre = RegistreExtracteurs()
    registre.enregistrer(ExtracteurPDF())
    return PipelineAnalyse(
        registre=registre,
        chercheur=ChercheurArticlesFTS5(depot),
        generateur=GenerateurOllama(),
        depot=depot,
        verificateur=VerificateurStandard(depot),
    )


def _numeros_valides(rapport) -> set[str]:
    """Retourne l'ensemble des numeros d'articles VALIDES (normalises)."""
    numeros = set()
    for v in rapport.citations_valides:
        try:
            numeros.add(normaliser_numero(v.citation.numero))
        except Exception:
            continue
    return numeros


def _evaluer_dossier(
    dossier: dict,
    pipeline: PipelineAnalyse,
    date_reference: date,
    workdir: Path,
) -> dict:
    dossier_dir = workdir / dossier["id"]
    dossier_dir.mkdir(parents=True, exist_ok=True)
    pdf = dossier_dir / "dossier.pdf"
    _creer_pdf(dossier["texte"], pdf)

    t0 = time.perf_counter()
    try:
        rapport, _ = pipeline.executer(dossier_dir, date_reference)
    except Exception as exc:
        return {
            "id": dossier["id"],
            "statut": "erreur",
            "erreur": str(exc),
            "duree_s": time.perf_counter() - t0,
            "citations_valides": [],
            "must_cite": dossier["must_cite"],
            "trouve": [],
            "manquant": dossier["must_cite"],
            "reussi": False,
        }
    duree = time.perf_counter() - t0

    valides = _numeros_valides(rapport)
    must_cite_norm = {normaliser_numero(n) for n in dossier["must_cite"]}
    trouve = valides & must_cite_norm
    manquant = must_cite_norm - valides

    return {
        "id": dossier["id"],
        "statut": "ok",
        "duree_s": duree,
        "citations_valides": sorted(valides),
        "must_cite": sorted(must_cite_norm),
        "trouve": sorted(trouve),
        "manquant": sorted(manquant),
        "reussi": len(trouve) > 0,
    }


def main(fichier: Path) -> int:
    if not fichier.exists():
        print(f"Fichier introuvable : {fichier}")
        return 1

    chemin_db = paths.VECTOR / "legi_full.sqlite"
    if not chemin_db.exists():
        print(f"Corpus complet absent : {chemin_db}")
        print("Lance d'abord : PYTHONPATH=. python scripts/telecharger_corpus.py")
        return 1

    dossiers = _charger_dossiers(fichier)
    print(f"Jeu de test  : {fichier}")
    print(f"Dossiers     : {len(dossiers)}")
    print()

    depot = DepotSQLite(chemin_db)
    print(f"Corpus       : {depot.compter()} articles")
    print()
    print("Lancement du benchmark (peut prendre plusieurs minutes)...")
    print()

    pipeline = _construire_pipeline(depot)
    date_reference = date.today()
    resultats = []

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for i, dossier in enumerate(dossiers, 1):
            print(f"  [{i}/{len(dossiers)}] {dossier['id']}...", end=" ", flush=True)
            r = _evaluer_dossier(dossier, pipeline, date_reference, workdir)
            resultats.append(r)
            if r["statut"] == "erreur":
                print(f"ERREUR ({r['erreur']})")
            else:
                marque = "OK" if r["reussi"] else "ECHEC"
                print(f"{marque} ({r['duree_s']:.1f}s, "
                      f"trouve={r['trouve']}, manquant={r['manquant']})")

    # Metriques
    n_total = len(resultats)
    n_reussis = sum(1 for r in resultats if r["reussi"])
    n_erreurs = sum(1 for r in resultats if r["statut"] == "erreur")
    durees = [r["duree_s"] for r in resultats if r["statut"] == "ok"]

    rappel = n_reussis / n_total * 100 if n_total else 0.0
    duree_moy = sum(durees) / len(durees) if durees else 0.0
    duree_max = max(durees) if durees else 0.0

    print()
    print("=== Resultats ===")
    print(f"Dossiers total    : {n_total}")
    print(f"Dossiers reussis  : {n_reussis}")
    print(f"Dossiers echoues  : {n_total - n_reussis - n_erreurs}")
    print(f"Dossiers en erreur: {n_erreurs}")
    print(f"Rappel            : {rappel:.1f} %")
    print(f"Duree moyenne     : {duree_moy:.1f} s")
    print(f"Duree max         : {duree_max:.1f} s")
    print()

    # Ecriture JSON
    sortie = paths.TMP / "bench_qualite.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(
        json.dumps(
            {
                "fichier": str(fichier),
                "date": date_reference.isoformat(),
                "n_total": n_total,
                "n_reussis": n_reussis,
                "rappel_pct": rappel,
                "duree_moyenne_s": duree_moy,
                "duree_max_s": duree_max,
                "resultats": resultats,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Resultats ecrits  : {sortie}")
    return 0 if n_reussis == n_total else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fichier", type=Path, default=_CHEMIN_DEFAUT)
    args = parser.parse_args()
    raise SystemExit(main(args.fichier))
