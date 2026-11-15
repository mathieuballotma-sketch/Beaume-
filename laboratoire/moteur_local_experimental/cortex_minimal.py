"""cortex_minimal.py — Coordinateur d etapes pour le parcours Beaume.

Cycle de vie : llama-completion est sans etat, il demarre et s arrete a chaque
appel. Pas de processus resident, pas de cache de prompt. Cette limite est
declaree, pas cachee.

Reprise sur erreur : une page en echec est journalisee, les suivantes
continuent. Le statut global distingue "ok" et "partiel".
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Etape:
    nom: str
    debut: str
    duree_s: float
    statut: str
    details: dict = field(default_factory=dict)


class Journal:
    def __init__(self):
        self.etapes = []

    @contextmanager
    def mesurer(self, nom):
        debut = datetime.now().isoformat(timespec="seconds")
        t0 = time.monotonic()
        etat = {"statut": "ok", "details": {}}
        try:
            yield etat
        except Exception as exc:
            etat["statut"] = "erreur"
            etat["details"]["erreur"] = str(exc)[:300]
            raise
        finally:
            self.etapes.append(Etape(
                nom=nom, debut=debut,
                duree_s=round(time.monotonic() - t0, 3),
                statut=etat["statut"], details=etat["details"],
            ))

    def ajouter(self, nom, statut, details=None, duree_s=0.0):
        self.etapes.append(Etape(
            nom=nom,
            debut=datetime.now().isoformat(timespec="seconds"),
            duree_s=duree_s, statut=statut,
            details=details or {},
        ))

    def serialiser(self):
        return [asdict(e) for e in self.etapes]


def executer_cortex(*, pdf=None, corpus_chemin=None, modele=None, pages=None):
    journal = Journal()

    from parcours_vertical_v1 import (
        CORPUS_DEFAUT, MODELE_DEFAUT, PDF_DEFAUT,
        charger_corpus, extraire_affirmations, inventaire_pdf, rapprocher,
    )
    from profil_materiel import choisir_profil, detecter_materiel

    pdf = Path(pdf) if pdf else PDF_DEFAUT
    corpus_chemin = Path(corpus_chemin) if corpus_chemin else CORPUS_DEFAUT
    modele = Path(modele) if modele else MODELE_DEFAUT

    with journal.mesurer("detection_materiel") as etat:
        materiel = detecter_materiel()
        taille = modele.stat().st_size / (1024 ** 3) if modele.is_file() else 2.0
        profil = choisir_profil(materiel, taille)
        etat["details"] = {"materiel": asdict(materiel), "profil": asdict(profil)}

    try:
        with journal.mesurer("inventaire_pdf") as etat:
            inventaire = inventaire_pdf(pdf, pages=pages)
            etat["details"] = {
                "n_passages": len(inventaire["passages"]),
                "sha_piece": inventaire["sha_piece"],
            }
    except Exception as exc:
        return {
            "etat_global": "echec",
            "raison": "inventaire_pdf : " + str(exc)[:300],
            "journal": journal.serialiser(),
        }

    with journal.mesurer("charger_corpus") as etat:
        corpus = charger_corpus(corpus_chemin)
        etat["details"] = {"n_articles": len(corpus)}

    journal.ajouter(
        "cycle_vie_modele", "ok",
        {"note": "llama-completion sans etat ; pas de processus resident"},
    )

    resultats = []
    for passage in inventaire["passages"]:
        page = passage["page"]
        methode = passage.get("methode_extraction", "inconnu")
        coords = passage.get("coordonnees")
        with journal.mesurer(f"page_{page}") as etat:
            if methode.startswith("echec_ocr"):
                etat["statut"] = "echec_ocr"
                resultats.append({
                    "page": page, "statut": "echec_ocr",
                    "methode_extraction": methode,
                    "coordonnees": coords,
                    "raison": methode,
                    "duree_modele_s": 0.0,
                })
                continue
            try:
                extraction = extraire_affirmations(passage, profil, modele)
            except Exception as exc:
                etat["statut"] = "erreur"
                etat["details"]["erreur"] = str(exc)[:300]
                resultats.append({
                    "page": page, "statut": "erreur",
                    "raison": str(exc)[:300],
                })
                continue

            st = extraction.get("etat")

            if st in ("erreur_modele", "erreur_json", "erreur_schema",
                      "erreur_validation"):
                etat["statut"] = st
                resultats.append({
                    "page": page, "statut": st,
                    "methode_extraction": methode,
                    "coordonnees": coords,
                    "raison": extraction.get("raison"),
                    "duree_modele_s": extraction.get("duree_secondes", 0),
                })
                continue

            if extraction.get("non_extraites"):
                etat["statut"] = "non_extraites"
                resultats.append({
                    "page": page, "statut": "non_extraites",
                    "methode_extraction": methode,
                    "coordonnees": coords,
                    "raison": "le modele n'a retourne aucune affirmation",
                    "duree_modele_s": extraction.get("duree_secondes", 0),
                })
                continue

            retenues = extraction.get("affirmations_retenues", [])
            hc = extraction.get("affirmations_hors_condition", [])
            nr = extraction.get("affirmations_non_retrouvees_dans_page", [])
            ap = extraction.get("affirmations_approximatives", [])
            nd = extraction.get("affirmations_negation_divergente", [])
            statut_page = st if st in ("ok", "hors_condition", "signaux_a_examiner") else "ok"

            rapprochements = [
                {"affirmation": aff, "rapprochement": rapprocher(aff, corpus)}
                for aff in retenues
            ]
            etat["details"] = {
                "n_retenues": len(retenues),
                "n_hors_condition": len(hc),
                "n_non_retrouvees": len(nr),
                "duree_modele_s": extraction.get("duree_secondes"),
            }
            resultats.append({
                "page": page, "statut": statut_page,
                "methode_extraction": methode,
                "coordonnees": coords,
                "affirmations_retenues": retenues,
                "affirmations_hors_condition": hc,
                "affirmations_non_retrouvees_dans_page": nr,
                "affirmations_approximatives": ap,
                "affirmations_negation_divergente": nd,
                "rapprochements": rapprochements,
                "duree_modele_s": extraction.get("duree_secondes", 0),
            })

    
    with journal.mesurer("contradictions") as etat:
        from detecter_contradictions import detecter_contradictions
        affs_pour_detection = []
        for pg in resultats:
            for aff in pg.get("affirmations_retenues", []):
                a = dict(aff)
                a["page"] = pg["page"]
                affs_pour_detection.append(a)
        contradictions = detecter_contradictions(affs_pour_detection)
        etat["details"] = {
            "n_affirmations": len(affs_pour_detection),
            "n_contradictions": len(contradictions),
        }

    with journal.mesurer("dates_divergentes") as etat:
        from detecter_dates import detecter_dates_divergentes
        dates_div = detecter_dates_divergentes(affs_pour_detection)
        etat["details"] = {
            "n_affirmations": len(affs_pour_detection),
            "n_dates_divergentes": len(dates_div),
        }

    from collections import Counter
    statuts = dict(Counter(r["statut"] for r in resultats))
    a_erreur = any(s.startswith("erreur") for s in statuts)
    a_echec_ocr = statuts.get("echec_ocr", 0) > 0
    etat_global = "partiel" if (a_erreur or a_echec_ocr) else "ok"
    n_total = len(inventaire["passages"])
    n_echecs = statuts.get("echec_ocr", 0)
    n_lues = 0
    for _r in resultats:
        if _r["statut"] == "echec_ocr":
            continue
        if str(_r.get("methode_extraction", "")).startswith("echec_ocr"):
            continue
        n_lues += 1
    couverture = {
        "pages_total": n_total,
        "pages_lues": n_lues,
        "pages_echec_ocr": n_echecs,
        "ratio": round(n_lues / max(n_total, 1), 3),
    }

    return {
        "etat_global": etat_global,
        "piece": inventaire["piece"],
        "sha_piece": inventaire["sha_piece"],
        "materiel": asdict(materiel),
        "profil": asdict(profil),
        "statuts_pages": statuts,
        "pages": resultats,
        "contradictions": contradictions,
        "dates_divergentes": dates_div,
        "couverture": couverture,
        "journal": journal.serialiser(),
    }


if __name__ == "__main__":
    import json
    import sys
    pages = [int(x) for x in sys.argv[1:]] or [2, 3, 4]
    r = executer_cortex(pages=pages)
    print(json.dumps(r, ensure_ascii=False, indent=2))
