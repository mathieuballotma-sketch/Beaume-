"""Benchmark de bout en bout sur des dossiers factuels synthetiques.

Les references `must_cite` sont positives et non exhaustives. Le rapport
mesure le rappel des references requises, sans assimiler les autres
citations a des faux positifs. Une execution de ce script est un test
operationnel sur le jeu indique, pas une validation juridique generale.

Le modele Ollama est parametrable via --modele (defaut : qwen-beaume-v1).
Le nom du modele est trace dans le rapport JSON pour eviter de comparer
deux executions produites par des modeles differents sans le savoir.

Separation score / disputed (version 3 du jeu de test) :
- Chaque dossier porte un `statut_annotation` : "provisoire" (defaut),
  "disputed", ou autre.
- Le score principal est calcule sur les dossiers != "disputed".
- Les dossiers "disputed" sont rapportes separement, pour information,
  et exclus du score principal. Cela documente un doute sur
  l'annotation sans pretendre qu'elle est fausse.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.generateur_ollama import GenerateurOllama
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.bench.metriques import (
    ReferenceArticle,
    charger_references_dossier,
    cle_article,
)
from beaume.config import paths
from beaume.ports.registre import RegistreExtracteurs


FICHIER_DEFAUT = Path(__file__).resolve().parents[1] / "beaume" / "bench" / "dossiers_test.json"
MODELE_DEFAUT = "qwen-beaume-v1"
STATUT_ANNOTATION_DEFAUT = "provisoire"
STATUT_DISPUTED = "disputed"


class _ChercheurTrace:
    """Decorateur de benchmark qui garde les hits de chaque chunk."""

    def __init__(self, chercheur: ChercheurArticlesFTS5) -> None:
        self.chercheur = chercheur
        self.appels: list[list[Any]] = []

    def reinitialiser(self) -> None:
        self.appels.clear()

    def chercher(self, texte: str, limite: int = 5) -> list[Any]:
        resultats = self.chercheur.chercher(texte, limite=limite)
        self.appels.append(resultats)
        return resultats


def _charger_jeu(chemin: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with chemin.open(encoding="utf-8") as fichier:
        data = json.load(fichier)
    if not isinstance(data, dict) or not isinstance(data.get("dossiers"), list):
        raise ValueError("Le fichier doit contenir une liste 'dossiers'.")
    meta = data.get("_meta", {})
    if not isinstance(meta, dict):
        raise ValueError("La metadonnee '_meta' doit etre un objet.")
    dossiers = data["dossiers"]
    if not dossiers:
        raise ValueError("Le jeu ne contient aucun dossier.")
    for i, dossier in enumerate(dossiers, start=1):
        if not isinstance(dossier, dict) or not dossier.get("texte"):
            raise ValueError(f"Dossier {i} invalide : texte manquant.")
        dossier.setdefault("id", f"dossier-{i:03d}")
        dossier.setdefault("statut_annotation", STATUT_ANNOTATION_DEFAUT)
        charger_references_dossier(dossier, meta.get("code"))
    return meta, dossiers


def _creer_pdf(texte: str, chemin: Path) -> None:
    """Ecrit un dossier de test dans un PDF et refuse le texte tronque."""
    document = pymupdf.open()
    try:
        page = document.new_page()
        rect = pymupdf.Rect(50, 50, 545, 780)
        hauteur_restante = page.insert_textbox(rect, texte, fontsize=11)
        if hauteur_restante < 0:
            raise ValueError("Le texte de test depasse la page PDF temporaire.")
        document.save(str(chemin))
    finally:
        document.close()

    with pymupdf.open(str(chemin)) as verif:
        texte_extrait = "\n".join(page.get_text() for page in verif)
    mots_attendus = {mot.casefold() for mot in texte.split() if len(mot) >= 5}
    mots_extraits = {mot.casefold() for mot in texte_extrait.split()}
    manquants = mots_attendus - mots_extraits
    if manquants:
        raise ValueError(
            "Le PDF temporaire ne contient pas tous les mots du dossier de test."
        )


def _construire_pipeline(depot: DepotSQLite, modele: str) -> PipelineAnalyse:
    registre = RegistreExtracteurs()
    registre.enregistrer(ExtracteurPDF())
    chercheur = _ChercheurTrace(ChercheurArticlesFTS5(depot))
    return PipelineAnalyse(
        registre=registre,
        chercheur=chercheur,
        generateur=GenerateurOllama(modele=modele),
        depot=depot,
        verificateur=VerificateurStandard(depot),
    )


def _cle_verification(verification: Any) -> ReferenceArticle | None:
    citation = verification.citation
    code = getattr(citation.code, "value", citation.code)
    numero = citation.numero
    if not str(code or "").strip() or not str(numero or "").strip():
        return None
    try:
        return cle_article(str(code), str(numero))
    except (TypeError, ValueError):
        # Une sortie LLM invalide doit être consignée comme rejetée, pas faire
        # échouer le benchmark qui est justement chargé de la diagnostiquer.
        return None


def _diagnostic_couverture(
    references: set[ReferenceArticle],
    candidats: set[ReferenceArticle],
) -> dict[str, Any]:
    trouvees = references & candidats
    absentes = references - candidats
    return {
        "references_must_cite_dans_candidats": [list(x) for x in sorted(trouvees)],
        "references_must_cite_absentes_des_candidats": [list(x) for x in sorted(absentes)],
        "rappel_retrieval_must_cite": len(trouvees) / len(references) if references else 0.0,
    }


def _diagnostic_recherche(
    pipeline: PipelineAnalyse,
    date_reference: date,
    references: set[ReferenceArticle],
) -> dict[str, Any]:
    chercheur = pipeline.analyseur.chercheur
    if not isinstance(chercheur, _ChercheurTrace):
        return {
            "n_appels_recherche": 0,
            "limite_par_chunk": pipeline.analyseur.limite_articles,
            "limite_candidats_total": getattr(
                pipeline.analyseur, "limite_candidats", None,
            ),
            "candidats_fts5_par_chunk": [],
            "candidats_transmis_au_llm": [],
            **_diagnostic_couverture(references, set()),
        }

    candidats_par_chunk = []
    for index, resultats in enumerate(chercheur.appels, start=1):
        candidats_fts5 = []
        for resultat in resultats:
            cle = cle_article(resultat.code, resultat.numero)
            candidats_fts5.append({
                "article_id": resultat.article_id,
                "code": cle[0],
                "numero": cle[1],
            })
        candidats_par_chunk.append({
            "chunk": index,
            "candidats_fts5": candidats_fts5,
        })

    # Utilise exactement le classement et le plafond de candidats de
    # l'analyseur. Sinon le benchmark surestime la couverture réellement
    # visible par le modele sur un dossier contenant beaucoup de chunks.
    articles_transmis = pipeline.analyseur._enrichir_articles(
        chercheur.appels, date_reference,
    )
    candidats_transmis: set[ReferenceArticle] = set()
    for article in articles_transmis:
        version = article.version_a(date_reference)
        if version is None:
            continue
        candidats_transmis.add(
            cle_article(article.code.value, version.numero)
        )

    return {
        "n_appels_recherche": len(chercheur.appels),
        "limite_par_chunk": pipeline.analyseur.limite_articles,
        "limite_candidats_total": pipeline.analyseur.limite_candidats,
        "candidats_fts5_par_chunk": candidats_par_chunk,
        "candidats_transmis_au_llm": [
            list(x) for x in sorted(candidats_transmis)
        ],
        **_diagnostic_couverture(references, candidats_transmis),
    }


def _diagnostic_citations(
    rapport: Any,
    candidats_transmis: set[ReferenceArticle],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    details = []
    compteurs: Counter[str] = Counter()
    for verification in rapport.verifications:
        citation = verification.citation
        cle = _cle_verification(verification)
        statut = verification.statut.value
        compteurs[statut] += 1
        details.append({
            "code": citation.code.value,
            "numero": citation.numero,
            "statut_verification": statut,
            "est_valide": verification.est_valide,
            "article_dans_candidats": (
                cle in candidats_transmis if cle is not None else False
            ),
            "extrait_fourni": bool((citation.extrait or "").strip()),
        })
    return details, dict(sorted(compteurs.items()))


def _evaluer_dossier(
    dossier: dict[str, Any],
    meta: dict[str, Any],
    pipeline: PipelineAnalyse,
    date_reference: date,
    workdir: Path,
) -> dict[str, Any]:
    statut_annotation = dossier.get("statut_annotation", STATUT_ANNOTATION_DEFAUT)
    gold = charger_references_dossier(dossier, meta.get("code"))
    chercheur = pipeline.analyseur.chercheur
    if isinstance(chercheur, _ChercheurTrace):
        chercheur.reinitialiser()
    dossier_dir = workdir / str(dossier["id"])
    dossier_dir.mkdir(parents=True, exist_ok=True)
    _creer_pdf(dossier["texte"], dossier_dir / "dossier.pdf")

    debut = time.perf_counter()
    try:
        rapport, _ = pipeline.executer(dossier_dir, date_reference)
    except Exception as exc:
        diagnostic_recherche = _diagnostic_recherche(
            pipeline, date_reference, gold,
        )
        return {
            "id": dossier["id"],
            "statut_annotation": statut_annotation,
            "statut_execution": "erreur",
            "type_erreur": type(exc).__name__,
            "duree_s": time.perf_counter() - debut,
            "references": [list(x) for x in sorted(gold)],
            "references_valides_trouvees": [],
            "references_manquantes": [list(x) for x in sorted(gold)],
            "nb_citations_rejetees": 0,
            "citations_detail": [],
            "statuts_citations": {},
            **diagnostic_recherche,
        }

    duree = time.perf_counter() - debut
    diagnostic_recherche = _diagnostic_recherche(
        pipeline, date_reference, gold,
    )
    candidats_transmis = {
        tuple(reference)
        for reference in diagnostic_recherche["candidats_transmis_au_llm"]
    }
    citations_detail, statuts_citations = _diagnostic_citations(
        rapport, candidats_transmis,
    )
    predictions = {
        cle
        for verification in rapport.verifications
        if verification.est_valide
        if (cle := _cle_verification(verification)) is not None
    }
    trouve = gold & predictions
    return {
        "id": dossier["id"],
        "statut_annotation": statut_annotation,
        "statut_execution": "ok",
        "duree_s": duree,
        "references": [list(x) for x in sorted(gold)],
        "references_valides_trouvees": [list(x) for x in sorted(trouve)],
        "references_manquantes": [list(x) for x in sorted(gold - predictions)],
        "nb_citations_generees": len(rapport.verifications),
        "nb_citations_valides": len(rapport.citations_valides),
        "nb_citations_rejetees": len(rapport.citations_rejetees),
        "nb_citations_valides_hors_must_cite": len(predictions - gold),
        "rappel_must_cite": len(trouve) / len(gold) if gold else 0.0,
        "citations_detail": citations_detail,
        "statuts_citations": statuts_citations,
        "modele": rapport.modele_llm,
        **diagnostic_recherche,
    }


def _calculer_agregats(resultats: list[dict[str, Any]]) -> dict[str, Any]:
    total_gold = sum(len(r["references"]) for r in resultats)
    total_hits = sum(len(r["references_valides_trouvees"]) for r in resultats)
    total_retrieval_hits = sum(
        len(r.get("references_must_cite_dans_candidats", []))
        for r in resultats
    )
    total_cases = len(resultats)
    erreurs = sum(r["statut_execution"] == "erreur" for r in resultats)
    statuts_citations: Counter[str] = Counter()
    for resultat in resultats:
        statuts_citations.update(resultat.get("statuts_citations", {}))
    succes_partiel = sum(bool(r["references_valides_trouvees"]) for r in resultats)
    succes_complet = sum(
        set(map(tuple, r["references_valides_trouvees"])) == set(map(tuple, r["references"]))
        for r in resultats
    )
    return {
        "n_dossiers": total_cases,
        "n_erreurs_execution": erreurs,
        "n_references_must_cite": total_gold,
        "rappel_micro_must_cite": total_hits / total_gold if total_gold else 0.0,
        "n_references_must_cite_dans_candidats": total_retrieval_hits,
        "rappel_micro_retrieval_must_cite": (
            total_retrieval_hits / total_gold if total_gold else 0.0
        ),
        "rappel_macro_must_cite": (
            sum(r["rappel_must_cite"] for r in resultats if "rappel_must_cite" in r)
            / total_cases if total_cases else 0.0
        ),
        "taux_dossiers_avec_au_moins_une_reference": (
            succes_partiel / total_cases if total_cases else 0.0
        ),
        "taux_dossiers_avec_toutes_les_references": (
            succes_complet / total_cases if total_cases else 0.0
        ),
        "n_citations_rejetees": sum(r.get("nb_citations_rejetees", 0) for r in resultats),
        "statuts_citations": dict(sorted(statuts_citations.items())),
        "n_citations_valides_hors_must_cite": sum(
            r.get("nb_citations_valides_hors_must_cite", 0) for r in resultats
        ),
        "duree_moyenne_s": (
            sum(r.get("duree_s", 0.0) for r in resultats if r["statut_execution"] == "ok")
            / max(1, sum(r["statut_execution"] == "ok" for r in resultats))
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fichier", type=Path, default=FICHIER_DEFAUT)
    parser.add_argument("--base", type=Path, default=paths.VECTOR / "legi_full.sqlite")
    parser.add_argument("--date-reference", type=date.fromisoformat, default=None)
    parser.add_argument("--sortie", type=Path, default=None)
    parser.add_argument(
        "--modele",
        default=MODELE_DEFAUT,
        help="Modele Ollama a tester (defaut : qwen-beaume-v1).",
    )
    args = parser.parse_args()
    if not args.fichier.is_file():
        parser.error(f"Jeu de test introuvable : {args.fichier}")
    if not args.base.is_file():
        parser.error(f"Corpus introuvable : {args.base}")

    meta, dossiers = _charger_jeu(args.fichier)
    date_brute = args.date_reference or meta.get("date_reference")
    if isinstance(date_brute, str):
        date_reference = date.fromisoformat(date_brute)
    elif isinstance(date_brute, date):
        date_reference = date_brute
    else:
        parser.error(
            "Date non definie : fournir --date-reference ou _meta.date_reference."
        )

    n_disputed = sum(
        1 for d in dossiers if d.get("statut_annotation") == STATUT_DISPUTED
    )
    n_score = len(dossiers) - n_disputed
    print(
        f"Dossiers : {len(dossiers)} (score : {n_score}, disputed : {n_disputed}) "
        f"| references : {meta.get('statut_annotations', 'non documente')}"
    )
    print(f"Corpus   : {DepotSQLite(args.base, lecture_seule=True).compter()} articles "
          f"| date : {date_reference.isoformat()}")
    print(f"Modele   : {args.modele}")

    depot = DepotSQLite(args.base, lecture_seule=True)
    pipeline = _construire_pipeline(depot, args.modele)

    resultats: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="beaume-bench-") as tmp:
        workdir = Path(tmp)
        for i, dossier in enumerate(dossiers, start=1):
            statut = dossier.get("statut_annotation", STATUT_ANNOTATION_DEFAUT)
            marqueur = f" [{statut}]" if statut != STATUT_ANNOTATION_DEFAUT else ""
            print(f"[{i}/{len(dossiers)}] {dossier['id']}{marqueur}...", end=" ", flush=True)
            resultat = _evaluer_dossier(dossier, meta, pipeline, date_reference, workdir)
            resultats.append(resultat)
            if resultat["statut_execution"] == "erreur":
                print(f"ERREUR ({resultat['type_erreur']})")
            else:
                print(
                    f"rappel must_cite={resultat['rappel_must_cite']:.0%}, "
                    f"retrieval={resultat['rappel_retrieval_must_cite']:.0%}, "
                    f"rejetees={resultat['nb_citations_rejetees']}"
                )

    resultats_score = [
        r for r in resultats if r.get("statut_annotation") != STATUT_DISPUTED
    ]
    resultats_disputed = [
        r for r in resultats if r.get("statut_annotation") == STATUT_DISPUTED
    ]
    metriques_score = _calculer_agregats(resultats_score)
    metriques_disputed = _calculer_agregats(resultats_disputed)
    metriques_globales = _calculer_agregats(resultats)

    resultat_final = {
        "type_evaluation": "pipeline_complet_synthetique",
        "jeu": str(args.fichier),
        "statut_annotations": meta.get("statut_annotations", "non_documente"),
        "date_reference": date_reference.isoformat(),
        "corpus": str(args.base),
        "n_articles_corpus": depot.compter(),
        "modele": args.modele,
        "n_dossiers_score": len(resultats_score),
        "n_dossiers_disputed": len(resultats_disputed),
        "metriques_score": metriques_score,
        "metriques_disputed": metriques_disputed,
        "metriques_globales_pour_reference": metriques_globales,
        "resultats": resultats,
        "interpretation": (
            "Les must_cite sont des references positives non exhaustives et "
            "non relues par un juriste. Le score principal exclut les dossiers "
            "marques 'disputed', dont l'annotation est contestee et documentee. "
            "Ces chiffres sont un diagnostic sur ce petit jeu synthetique, pas "
            "une validation juridique."
        ),
    }
    sortie = args.sortie or paths.TMP / f"bench_qualite_{args.modele.replace(':', '_')}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(resultat_final, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=== Score principal (dossiers non disputed) ===")
    print(f"  Dossiers              : {metriques_score['n_dossiers']}")
    print(f"  Rappel micro must_cite: {metriques_score['rappel_micro_must_cite']:.1%}")
    print(f"  Rappel macro must_cite: {metriques_score['rappel_macro_must_cite']:.1%}")
    print(f"  Retrieval must_cite   : {metriques_score['rappel_micro_retrieval_must_cite']:.1%}")
    print(f"  Citations rejetees    : {metriques_score['n_citations_rejetees']}")

    if resultats_disputed:
        print()
        print("=== Dossiers disputed (non comptes dans le score) ===")
        print(f"  Dossiers              : {metriques_disputed['n_dossiers']}")
        print(f"  Rappel micro must_cite: {metriques_disputed['rappel_micro_must_cite']:.1%}")
        print(f"  Rappel macro must_cite: {metriques_disputed['rappel_macro_must_cite']:.1%}")
        print(f"  Retrieval must_cite   : {metriques_disputed['rappel_micro_retrieval_must_cite']:.1%}")

    print()
    print(f"Rapport : {sortie}")
    return 1 if metriques_score["n_erreurs_execution"] else 0


if __name__ == "__main__":
    raise SystemExit(main())