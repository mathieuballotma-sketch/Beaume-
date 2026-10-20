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
import hashlib
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from beaume.config import paths
from beaume.legal.normalisation import normaliser_numero

CHEMIN_FAITS_DEFAUT = paths.DATA / "training" / "faits_clients_propres.jsonl"
CHEMIN_SORTIE = paths.DATA / "training" / "dataset_entrainement.parquet"
CHEMIN_MANIFESTE = paths.DATA / "training" / "dataset_entrainement_manifest.json"
CHEMIN_DB = paths.VECTOR / "legi_full.sqlite"
TAILLE_MAX_ARTICLE = 2000


def _charger_articles(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Indexe les versions par numero, sans perdre les codes concurrents."""
    print("Chargement des articles en memoire...")
    articles: dict[str, list[dict]] = {}
    for ligne in conn.execute("""
        SELECT a.id AS article_id, a.code AS code, v.numero AS numero,
               v.texte AS texte, v.date_debut AS date_debut,
               v.date_fin AS date_fin
        FROM articles a
        JOIN versions v ON v.article_id = a.id
        ORDER BY v.numero, a.code, a.id, v.date_debut
    """):
        try:
            numero = normaliser_numero(ligne["numero"])
        except (TypeError, ValueError):
            continue
        if not numero:
            continue
        articles.setdefault(numero, []).append(dict(ligne))
    print(
        f"  {sum(map(len, articles.values()))} versions chargees "
        f"pour {len(articles)} numeros normalises."
    )
    return articles


def _resoudre_article(
    articles: dict[str, list[dict]],
    reference: str | dict,
    date_fait: date,
) -> tuple[dict | None, str | None]:
    """Resout un article uniquement si code, numero et date le determinent."""
    if isinstance(reference, dict):
        numero_brut = reference.get("numero") or reference.get("article")
        code = reference.get("code")
    else:
        numero_brut = reference
        code = None
    if not isinstance(numero_brut, str) or not numero_brut.strip():
        return None, "reference_invalide"

    try:
        numero = normaliser_numero(numero_brut)
    except (TypeError, ValueError):
        return None, "reference_invalide"

    versions = articles.get(numero, [])
    if not versions:
        return None, "article_absent_du_corpus"
    if code:
        code_normalise = str(code).strip().lower()
        versions = [v for v in versions if str(v["code"]).strip().lower() == code_normalise]
        if not versions:
            return None, "code_absent_du_corpus"

    applicables = []
    for version in versions:
        try:
            debut = date.fromisoformat(str(version["date_debut"]))
            fin_brute = version.get("date_fin")
            fin = date.fromisoformat(str(fin_brute)) if fin_brute else None
        except (TypeError, ValueError):
            continue
        if debut <= date_fait and (fin is None or date_fait <= fin):
            applicables.append((version, debut))

    if not applicables:
        return None, "aucune_version_a_la_date"

    ids_articles = {v["article_id"] for v, _ in applicables}
    if len(ids_articles) != 1:
        return None, "reference_ambigue"

    # Une seule version par article doit s'appliquer. Si le corpus contient
    # des intervalles qui se chevauchent, on refuse aussi de choisir au hasard.
    if len(applicables) != 1:
        return None, "versions_chevauchantes"
    return applicables[0][0], None


def _construire_paires(
    chemin_faits: Path,
    articles: dict[str, list[dict]],
    max_par_fait: int,
) -> tuple[list[dict], dict]:
    """Construit la liste des paires (anchor, positive)."""
    paires: list[dict] = []
    n_faits = 0
    n_manquants = 0
    n_articles_absents = 0
    n_codes_absents = 0
    n_sans_version_date = 0
    n_references_invalides = 0
    n_ambigus = 0
    n_versions_chevauchantes = 0
    n_dates_invalides = 0
    n_lignes_ignorees = 0
    n_paires_article_tronque = 0
    articles_manquants: list[str] = []

    with chemin_faits.open(encoding="utf-8") as f_in:
        for ligne in f_in:
            try:
                d = json.loads(ligne)
            except json.JSONDecodeError:
                n_lignes_ignorees += 1
                continue

            if not isinstance(d, dict):
                n_lignes_ignorees += 1
                continue

            faits_bruts = d.get("faits_client")
            articles_cites = d.get("articles", [])
            id_fait = d.get("id", "")
            date_brute = d.get("date", "")

            if (
                not isinstance(faits_bruts, str)
                or not faits_bruts.strip()
                or not isinstance(articles_cites, list)
                or not articles_cites
                or not isinstance(id_fait, str)
                or not id_fait.strip()
            ):
                n_lignes_ignorees += 1
                continue
            faits = faits_bruts.strip()
            id_fait = id_fait.strip()

            try:
                date_fait = date.fromisoformat(str(date_brute))
            except (TypeError, ValueError):
                n_dates_invalides += 1
                n_lignes_ignorees += 1
                continue

            n_faits += 1
            n_ecrits = 0
            for reference in articles_cites:
                if n_ecrits >= max_par_fait:
                    break
                version, erreur = _resoudre_article(articles, reference, date_fait)
                if version is None:
                    if erreur in ("reference_ambigue", "versions_chevauchantes"):
                        if erreur == "reference_ambigue":
                            n_ambigus += 1
                        else:
                            n_versions_chevauchantes += 1
                    else:
                        n_manquants += 1
                        if erreur == "article_absent_du_corpus":
                            n_articles_absents += 1
                        elif erreur == "code_absent_du_corpus":
                            n_codes_absents += 1
                        elif erreur == "aucune_version_a_la_date":
                            n_sans_version_date += 1
                        else:
                            n_references_invalides += 1
                    numero_manquant = (
                        reference.get("numero") or reference.get("article")
                        if isinstance(reference, dict) else reference
                    )
                    articles_manquants.append(str(numero_manquant))
                    continue

                try:
                    numero = normaliser_numero(str(version["numero"]))
                except (TypeError, ValueError):
                    n_manquants += 1
                    articles_manquants.append(str(reference))
                    continue

                texte_article = version.get("texte")
                if not isinstance(texte_article, str) or not texte_article.strip():
                    n_manquants += 1
                    articles_manquants.append(str(reference))
                    continue
                tronque = len(texte_article) > TAILLE_MAX_ARTICLE
                if tronque:
                    n_paires_article_tronque += 1
                    texte_positif = texte_article[:TAILLE_MAX_ARTICLE - 3]
                    fin_mot = texte_positif.rfind(" ")
                    if fin_mot > 0:
                        texte_positif = texte_positif[:fin_mot]
                    texte_positif = texte_positif.rstrip() + "..."
                else:
                    texte_positif = texte_article

                paires.append({
                    "anchor": faits,
                    "positive": texte_positif,
                    "article_id": version["article_id"],
                    "article": numero,
                    "code": version["code"],
                    "id_fait": id_fait,
                    "date_fait": date_fait,
                    "positive_tronquee": tronque,
                })
                n_ecrits += 1

    stats = {
        "n_faits": n_faits,
        "n_paires": len(paires),
        "n_manquants": n_manquants,
        "n_articles_absents_du_corpus": n_articles_absents,
        "n_codes_absents_du_corpus": n_codes_absents,
        "n_sans_version_a_la_date": n_sans_version_date,
        "n_references_invalides": n_references_invalides,
        "n_references_ambigues": n_ambigus,
        "n_versions_chevauchantes": n_versions_chevauchantes,
        "n_dates_invalides": n_dates_invalides,
        "n_lignes_ignorees": n_lignes_ignorees,
        "n_paires_article_tronque": n_paires_article_tronque,
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

    if args.max_par_fait <= 0:
        parser.error("--max-par-fait doit etre strictement positif.")

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
        "db_articles_sha256": _sha256(CHEMIN_DB),
        "regle_resolution": (
            "code+numero+date si code fourni; sinon numero+date uniquement "
            "si un article unique est applicable"
        ),
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
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
