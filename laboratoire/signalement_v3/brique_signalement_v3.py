"""Brique de signalement v3 (laboratoire, deterministe).

Changements v3 vs v2 (contre-exemples Codex) :
- Concurrence visible des deux cotes : remplacement de l'appariement biparti glouton
  (dependait de l'ordre) par un comptage de candidats invariant par permutation.
  Un fait partage par plusieurs mentions rend TOUTES les mentions concernees
  'couvert_partage_ambigu'.
- Mois accentues : 'fevrier'/'février', 'aout'/'août', 'decembre'/'décembre'.
  Les offsets restent ceux de la chaine Python d'origine (pas d'octets).
- Exhaustivite preexistante : on verifie qu'elle n'a pas ete modifiee par la
  brique ; on ne rejette pas son existence. Pas d'AssertionError.
- Annee absente (G3) : une date partielle est une INCERTITUDE (score 1 -> ambiguite),
  pas une couverture silencieuse.
Regles de fond : ne modifie pas exhaustivite, pas de verdict moteur, pas d'appel
modele. Absence d'alerte n'est PAS une preuve d'exhaustivite.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
REG_REF = HERE / "registre_reference_v3.json"
REG_ENR = HERE / "registre_enrichi_v3.json"
CAS = HERE / "cas_test_v3.json"
ATTENTES = HERE / "attentes_test_v3.json"

MOIS_VARIANTES = {
    "janvier": 1,
    "fevrier": 2, "février": 2,
    "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "décembre": 12,
}
_MOIS_PATTERN = "|".join(sorted(MOIS_VARIANTES.keys(), key=len, reverse=True))
DATE_RE = re.compile(r'(\d{1,2})\s+(' + _MOIS_PATTERN + r')(?:\s+(\d{4}))?', re.IGNORECASE)
PHRASE_RE = re.compile(r'[.;!?]\s+')
SYSTEME_COORDS = ("offsets en caracteres Python (str) sur le texte_extrait, 0-indexe, "
                  "fin exclusive ; PAS des octets, PAS des coordonnees visuelles PDF")


def charger(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def empreinte(obj):
    if isinstance(obj, str):
        return hashlib.sha256(obj.encode("utf-8")).hexdigest()
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def extraire_dates(texte):
    out = []
    for m in DATE_RE.finditer(texte):
        jour = int(m.group(1))
        mois_num = MOIS_VARIANTES[m.group(2).lower()]
        annee = m.group(3)
        out.append({
            "valeur_brute": texte[m.start():m.end()],
            "position_debut": m.start(),
            "position_fin": m.end(),
            "jour": jour, "mois": mois_num,
            "annee": int(annee) if annee else None,
            "cle_jour_mois": "%02d-%02d" % (jour, mois_num),
        })
    return out


def parser_date_fait(d):
    v = d.get("valeur") or ""
    m = DATE_RE.search(v)
    if not m:
        return None
    return {
        "valeur_brute": m.group(0),
        "jour": int(m.group(1)),
        "mois": MOIS_VARIANTES[m.group(2).lower()],
        "annee": int(m.group(3)) if m.group(3) else None,
        "cle_jour_mois": "%02d-%02d" % (int(m.group(1)), MOIS_VARIANTES[m.group(2).lower()]),
        "role": d.get("role"),
    }


def dates_fait_parsees(fait):
    return [x for x in (parser_date_fait(d) for d in (fait.get("dates") or [])) if x]


def dates_compatibles(d_mention, d_fait):
    if d_mention["cle_jour_mois"] != d_fait["cle_jour_mois"]:
        return False
    a_m, a_f = d_mention["annee"], d_fait["annee"]
    if a_m is not None and a_f is not None:
        return a_m == a_f
    return "partielle"


def decouper_phrases(texte):
    phrases, start = [], 0
    for m in PHRASE_RE.finditer(texte):
        phrases.append((start, m.end())); start = m.end()
    if start < len(texte):
        phrases.append((start, len(texte)))
    return phrases


def phrase_pour(position, phrases):
    for s, e in phrases:
        if s <= position < e:
            return s, e
    return (0, max((e for _, e in phrases), default=0))


def extraire_mentions(texte, evenements_consideres, registre):
    mentions = []
    texte_lower = texte.lower()
    for event_type in evenements_consideres:
        config = registre["types_evenement"].get(event_type, {})
        used_spans = []
        for neg in config.get("negation_marqueurs", []):
            pos = 0
            while True:
                idx = texte_lower.find(neg.lower(), pos)
                if idx < 0: break
                mentions.append({"event_type": event_type, "position_debut": idx,
                                 "position_fin": idx + len(neg), "match_text": texte[idx:idx+len(neg)],
                                 "negated": True})
                used_spans.append((idx, idx + len(neg))); pos = idx + len(neg)
        for indicatif in config.get("indicatifs", []):
            pos = 0
            while True:
                idx = texte_lower.find(indicatif.lower(), pos)
                if idx < 0: break
                in_neg = any(ns <= idx and idx + len(indicatif) <= ne for ns, ne in used_spans)
                if not in_neg:
                    mentions.append({"event_type": event_type, "position_debut": idx,
                                     "position_fin": idx + len(indicatif),
                                     "match_text": texte[idx:idx+len(indicatif)], "negated": False})
                pos = idx + len(indicatif)
    return dedoublonner_mentions(mentions)


def dedoublonner_mentions(mentions):
    gardees = []
    for m in sorted(mentions, key=lambda x: (-(x["position_fin"] - x["position_debut"]),
                                            x["position_debut"])):
        if any(g["event_type"] == m["event_type"] and g["negated"] == m["negated"]
               and g["position_debut"] <= m["position_debut"]
               and m["position_fin"] <= g["position_fin"] for g in gardees):
            continue
        gardees.append(m)
    return sorted(gardees, key=lambda x: x["position_debut"])


def contexte(texte, debut, fin, marge=40):
    a, b = max(0, debut - marge), min(len(texte), fin + marge)
    return ("[...]" if a > 0 else "") + texte[a:b] + ("[...]" if b < len(texte) else "")


def analyser_candidats_par_mention(mentions, dates, phrases, faits):
    res = []
    for m in mentions:
        s, e = phrase_pour(m["position_debut"], phrases)
        dates_phrase = [d for d in dates if s <= d["position_debut"] < e]
        m["_dates_candidates"] = dates_phrase
        m["_phrase"] = (s, e)
        liste = []
        for fi, f in enumerate(faits):
            if f.get("evenement", {}).get("type") != m["event_type"]: continue
            if m["negated"] and f.get("polarite") != "nie": continue
            if (not m["negated"]) and f.get("polarite") == "nie": continue
            df = dates_fait_parsees(f)
            if df and dates_phrase:
                paires = [dates_compatibles(dm, dff) for dm in dates_phrase for dff in df]
                if any(x is True for x in paires):
                    liste.append((fi, 2, "coherente",
                                  "date de la mention compatible avec une date du fait"))
                elif any(x == "partielle" for x in paires):
                    liste.append((fi, 1, "date_partielle_non_verifiable",
                                  "annee absente d'un cote : incertitude, pas preuve"))
                else:
                    liste.append((fi, 0, "incompatible",
                                  "aucune date de la phrase ne correspond aux dates du fait"))
            elif df and not dates_phrase:
                liste.append((fi, 1, "non_verifiable_date_mention",
                              "aucune date dans la phrase de la mention ; fait date : indeterminable"))
            elif (not df) and dates_phrase:
                if m["negated"]:
                    liste.append((fi, 2, "coherente_negation_sans_date",
                                  "negation : dates de la mention non applicables ; fait sans date"))
                else:
                    liste.append((fi, 2, "coherente_sans_date_fait",
                                  "fait sans date ; mention datee : pas de contradiction de date"))
            else:
                liste.append((fi, 2, "coherente_sans_date",
                              "ni la mention ni le fait ne portent de date"))
        res.append(liste)
    return res


def decider_statut(liste, partage_par_fait):
    s2 = [(fi, st, mo) for fi, sc, st, mo in liste if sc == 2]
    s1 = [(fi, st, mo) for fi, sc, st, mo in liste if sc == 1]
    if s2:
        uniques = [(fi, st, mo) for fi, st, mo in s2 if partage_par_fait.get(fi, 0) == 1]
        if len(s2) == 1 and len(uniques) == 1:
            return "couvert_unique", "appariement unique avec fait index " + str(uniques[0][0])
        if not uniques:
            fi_partage = s2[0][0]
            return ("couvert_partage_ambigu",
                    "fait index " + str(fi_partage) + " partage avec "
                    + str(partage_par_fait.get(fi_partage, 1) - 1)
                    + " autre(s) mention(s) : concurrence visible")
        return ("couvert_ambigu",
                "concurrence : " + str(len(s2)) + " faits candidats de meme niveau ; uniques : "
                + str([fi for fi, _, _ in uniques]))
    if s1:
        if len(s1) == 1:
            fi, st, mo = s1[0]
            return "ambigu", st + " : " + mo
        return ("ambigu",
                "concurrence de " + str(len(s1)) + " candidats avec dates non verifiables")
    return ("non_couvert",
            "aucun fait annote du meme type et de meme polarite" if not liste
            else "tous les faits candidats ont une date incompatible avec la mention")


def snapshot_exhaustivite(faits):
    return [(i, f.get("exhaustivite")) for i, f in enumerate(faits) if "exhaustivite" in f]


def exhaustivite_preservee(faits, snapshot):
    return [(i, f.get("exhaustivite")) for i, f in enumerate(faits) if "exhaustivite" in f] == snapshot


def traiter_cas(cas, registre, registre_nom):
    fp_texte = empreinte(cas["texte_extrait"])
    fp_faits = empreinte(cas["faits_annotes"])
    snap_exh = snapshot_exhaustivite(cas["faits_annotes"])

    texte = cas["texte_extrait"]
    dates = extraire_dates(texte)
    phrases = decouper_phrases(texte)
    mentions = extraire_mentions(texte, cas["evenements_consideres"], registre)
    cand_par_mention = analyser_candidats_par_mention(mentions, dates, phrases, cas["faits_annotes"])

    partage_par_fait = {}
    for liste in cand_par_mention:
        for fi, sc, _, _ in liste:
            if sc == 2:
                partage_par_fait[fi] = partage_par_fait.get(fi, 0) + 1

    associations, alertes, ambiguites = [], [], []
    for mi, m in enumerate(mentions):
        statut, motif = decider_statut(cand_par_mention[mi], partage_par_fait)
        entry = {
            "mention_index": mi,
            "event_type": m["event_type"],
            "extrait": m["match_text"],
            "position_debut": m["position_debut"],
            "position_fin": m["position_fin"],
            "negated": m["negated"],
            "extrait_contexte": contexte(texte, m["position_debut"], m["position_fin"]),
            "phrase": {"debut": m["_phrase"][0], "fin": m["_phrase"][1]},
            "dates_candidates_phrase": [{"valeur_brute": d["valeur_brute"],
                                          "position_debut": d["position_debut"],
                                          "position_fin": d["position_fin"],
                                          "annee_presente": d["annee"] is not None}
                                         for d in m["_dates_candidates"]],
            "candidats": [{"fait_id": cas["faits_annotes"][fi].get("fait_id"),
                            "score": sc, "statut_date": st, "motif": mo}
                           for fi, sc, st, mo in cand_par_mention[mi]],
            "statut": statut,
            "motif": motif,
        }
        if statut == "non_couvert":
            entry["nature"] = "alerte"; alertes.append(entry)
        elif statut in ("ambigu", "couvert_ambigu", "couvert_partage_ambigu"):
            entry["nature"] = "ambiguite"; ambiguites.append(entry)
        else:
            entry["nature"] = "silence"
        associations.append(entry)

    assert empreinte(cas["texte_extrait"]) == fp_texte, "texte_extrait mute !"
    assert empreinte(cas["faits_annotes"]) == fp_faits, "faits_annotes mutes !"

    return {
        "cas_id": cas["id"], "origine": cas.get("origine"), "registre": registre_nom,
        "systeme_coordonnees": SYSTEME_COORDS,
        "mentions_detectees": [{"event_type": m["event_type"], "extrait": m["match_text"],
                                 "position_debut": m["position_debut"],
                                 "position_fin": m["position_fin"], "negated": m["negated"]}
                                for m in mentions],
        "associations": associations,
        "alertes": alertes, "ambiguites": ambiguites,
        "nb_mentions": len(mentions), "nb_alertes": len(alertes), "nb_ambiguites": len(ambiguites),
        "nb_couvert_unique": sum(1 for a in associations if a["statut"] == "couvert_unique"),
        "nb_couvert_partage_ambigu": sum(1 for a in associations if a["statut"] == "couvert_partage_ambigu"),
        "nb_couvert_ambigu": sum(1 for a in associations if a["statut"] == "couvert_ambigu"),
        "avertissement": ("une alerte n'est pas un fait ; l'absence d'alerte n'est pas preuve "
                          "d'exhaustivite ; une ambiguite n'est ni alerte ni silence ; une "
                          "date partielle (annee absente) est une incertitude, pas une preuve."),
        "non_contamination": {
            "texte_extrait_inchange": True,
            "faits_annotes_inchange": True,
            "verdict_moteur_non_appele": True,
            "exhaustivite_preexistante_detectee": [{"fait_index": i, "valeur": v} for i, v in snap_exh],
            "exhaustivite_preexistante_preservee": exhaustivite_preservee(cas["faits_annotes"], snap_exh),
        },
    }


def verifier_conformite(r, att):
    exp = att.get("conformite_technique_attendue")
    na = att.get("alertes_attendues", 0); nb = att.get("ambiguites_attendues", 0)
    al = r["nb_alertes"]; am = r["nb_ambiguites"]
    if exp == "alerte":
        ok = al >= 1 and am == 0
    elif exp == "ambiguite":
        ok = am >= 1 and al == 0
    elif exp == "alerte_et_ambiguite":
        ok = al >= 1 and am >= 1
    elif exp == "silence":
        ok = al == 0 and am == 0
    else:
        ok = False
    return {"statut_attendu": exp, "alertes_attendues": na, "alertes_obtenues": al,
            "ambiguites_attendues": nb, "ambiguites_obtenues": am,
            "statut_ok": ok, "nb_ok": ok and al == na and am == nb}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registre", choices=["reference", "enrichi"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cas-ids", default="")
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        print("ATTENTION : " + str(out) + " existe deja, non ecrase"); return 1
    reg = charger(REG_REF if args.registre == "reference" else REG_ENR)
    cas_data = charger(CAS); att_data = charger(ATTENTES)
    att_by = {(a["cas_id"], a["registre"]): a for a in att_data["attentes"]}
    filtre = set(x.strip() for x in args.cas_ids.split(",") if x.strip())
    a_traiter = [c for c in cas_data["cas"]
                  if (not filtre or c["id"] in filtre) and (c["id"], args.registre) in att_by]
    if not a_traiter:
        print("Aucun cas a traiter pour registre=" + args.registre); return 2
    resultats, n_ok, n_ecart = [], 0, 0
    for cas in a_traiter:
        r = traiter_cas(cas, reg, args.registre)
        conf = verifier_conformite(r, att_by[(cas["id"], args.registre)])
        r["attente"] = att_by[(cas["id"], args.registre)]; r["conformite"] = conf
        if conf["nb_ok"]: n_ok += 1
        else: n_ecart += 1
        resultats.append(r)
    out.write_text(json.dumps({
        "schema_version": "beaume.resultats_signalement/3",
        "registre": args.registre,
        "registre_sha256": hashlib.sha256(Path(REG_REF if args.registre=="reference" else REG_ENR).read_bytes()).hexdigest(),
        "systeme_coordonnees": SYSTEME_COORDS,
        "synthese": {"total": len(resultats), "conformes_nb": n_ok, "ecarts_nb": n_ecart,
                     "alertes_totales": sum(r["nb_alertes"] for r in resultats),
                     "ambiguites_totales": sum(r["nb_ambiguites"] for r in resultats),
                     "couvert_unique_totaux": sum(r["nb_couvert_unique"] for r in resultats),
                     "couvert_partage_ambigu_totaux": sum(r["nb_couvert_partage_ambigu"] for r in resultats),
                     "couvert_ambigu_totaux": sum(r["nb_couvert_ambigu"] for r in resultats)},
        "resultats": resultats,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK ecrit : " + out.name + " sha=" + hashlib.sha256(out.read_bytes()).hexdigest())
    print("Registre : " + args.registre)
    print("Cas traites : " + str(len(resultats)) + "  conformes : " + str(n_ok) + "  ecarts : " + str(n_ecart))
    return 0 if n_ecart == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
