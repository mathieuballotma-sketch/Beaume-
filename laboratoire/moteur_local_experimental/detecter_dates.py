"""detecter_dates.py — Detection deterministe de dates divergentes.

Deux affirmations qui partagent le meme dossier ET le meme objet mais
donnent des dates differentes pour un evenement de meme polarite sont
des "dates divergentes" a examiner.

Regles symetriques de detecter_contradictions :
- meme dossier exige
- meme objet exige (extrait par _objet_de_la_reception)
- meme polarite exige (deux receptions affirmees, ou deux transferts)
- dates differentes (ou l une ancree et l autre absente -> "date manquante")

Ne pas confondre avec contradiction : ici les deux phrases disent la meme
chose sur le fond, mais pas sur la date.
"""
from __future__ import annotations

from detecter_contradictions import (
    _dossiers,
    _objet_de_la_reception,
    _polarite,
)


def _date_normale(aff):
    d = (aff.get("date") or "").strip().lower()
    if d in ("", "inconnue", "inconnu"):
        return None
    return d


def detecter_dates_divergentes(affirmations_avec_page):
    par_dossier = {}
    for aff in affirmations_avec_page:
        for d in _dossiers(aff["texte"]):
            par_dossier.setdefault(d, []).append(aff)

    resultats = []
    for dossier, groupe in par_dossier.items():
        for i, a in enumerate(groupe):
            for b in groupe[i + 1:]:
                pa = _polarite(a["texte"])
                pb = _polarite(b["texte"])
                if pa == "neutre" or pb == "neutre" or pa != pb:
                    continue
                oa = _objet_de_la_reception(a["texte"])
                ob = _objet_de_la_reception(b["texte"])
                if not oa or oa != ob:
                    continue

                da = _date_normale(a)
                db = _date_normale(b)

                if da and db and da != db:
                    niveau = "date_divergente"
                    raison = (
                        "deux affirmations de meme polarite sur " + "/".join(sorted(oa))
                        + " (dossier " + dossier + ") mais dates differentes : "
                        + da + " vs " + db + " — a examiner : laquelle est la bonne ?"
                    )
                elif (da and not db) or (db and not da):
                    niveau = "date_manquante"
                    raison = (
                        "deux affirmations de meme polarite sur " + "/".join(sorted(oa))
                        + " (dossier " + dossier + ") dont une est datee ("
                        + (da or db) + ") et l autre non — a examiner"
                    )
                else:
                    continue

                resultats.append({
                    "dossier": dossier,
                    "niveau": niveau,
                    "page_a": a["page"], "page_b": b["page"],
                    "texte_a": a["texte"], "texte_b": b["texte"],
                    "date_a": da, "date_b": db,
                    "polarite": pa,
                    "objet": sorted(oa),
                    "raison": raison,
                })
    return resultats
