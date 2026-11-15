"""parcours_vertical_v1.py — Premiere tranche verticale Beaume.

PDF fictif -> inventaire -> passages -> affirmations (via modele local)
-> corpus juridique fictif -> rapprochement -> resultat structure.

Backend : llama-completion via premier_moteur. Modele : granite 3.1 dense 2B
(blob Ollama GGUF brut charge directement, pas via Ollama). Aucun cache de
prompt active. Aucune donnee reelle. Aucun fichier historique modifie.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import fitz

from verrou_cache import appel_modele_sans_cache as executer_llama_completion
from profil_materiel import (
    ConfigurationRefusee,
    MaterielInsuffisant,
    Profil,
    choisir_profil,
    detecter_materiel,
)
from schema_beaume import SchemaNonSupporte, generer_gbnf
from validateur_beaume import valider

ICI = Path(__file__).resolve().parent
MODELE_DEFAUT = Path.home() / ".ollama/models/blobs/sha256-5c56bb0256a2c402e95282a29bb5cb747bb805eda0e14a84b1f6c594a297ec1a"
PDF_DEFAUT = ICI / "experience_grand_pdf/dossier/dossier_fictif_24_pages.pdf"
CORPUS_DEFAUT = ICI / "corpus_juridique_fictif.json"

SCHEMA_AFFIRMATIONS = {
    "type": "object",
    "properties": {
        "affirmations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "date": {"type": "string"},
                    "personnes": {"type": "string"},
                },
                "required": ["texte", "date", "personnes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["affirmations"],
    "additionalProperties": False,
}

PROMPT_AFFIRMATIONS = 'Tu recois un passage de dossier fictif. N EXTRAIS QUE les phrases qui remplissent LES DEUX conditions suivantes :\n  1. la phrase contient une date explicite (ex: 3 avril 2024) ;\n  2. la phrase contient au moins une personne nommee (ex: Lina Morel) ou une societe nommee (ex: Nordex).\nIGNORE toutes les phrases de pure description, de classement, de renvoi documentaire, ou de mise en garde. Si aucune phrase ne remplit LES DEUX conditions, retourne une liste vide. N invente rien.\nPour chaque phrase retenue : texte (extrait exact), date (ISO YYYY-MM-DD ou inconnue), personnes (noms separes par point-virgule ou aucune).\nFormat JSON strict.\n\nPASSAGE:\n{passage}\n'



def charger_corpus(chemin: Path) -> list[dict]:
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def inventaire_pdf(chemin: Path, pages: Optional[list[int]] = None,
                    ocr_fallback: bool = True) -> dict:
    with open(chemin, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    doc = fitz.open(chemin)
    passages = []
    n_ocr = 0
    echecs_ocr = 0
    for i, page in enumerate(doc):
        num = i + 1
        if pages is not None and num not in pages:
            continue
        texte = page.get_text()
        methode = "pymupdf"
        coordonnees = None
        if ocr_fallback and len(texte.strip()) < 20:
            try:
                from ocr_vision import ocr_page_image
                texte, coordonnees = ocr_page_image(page, retour_coordonnees=True)
                methode = "ocr_vision"
                n_ocr += 1
            except Exception as exc:
                methode = "echec_ocr:" + str(exc)[:80]
                coordonnees = None
                echecs_ocr += 1
        passages.append({
            "piece": Path(chemin).name,
            "page": num,
            "sha_piece": sha,
            "texte": texte,
            "methode_extraction": methode,
            "coordonnees": coordonnees,
        })
    doc.close()
    return {
        "piece": Path(chemin).name,
        "sha_piece": sha,
        "passages": passages,
        "n_ocr": n_ocr,
        "echecs_ocr": echecs_ocr,
    }


def _contient_fait_concret(texte: str) -> bool:
    return bool(re.search(r"\b(19|20)\d{2}\b|\b\d{2,}\b", texte))


def _ecrire_grammaire(gbnf: str) -> str:
    fd, chemin = tempfile.mkstemp(prefix="beaume_gram_", suffix=".gbnf")
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        pass
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(gbnf)
    return chemin


def extraire_affirmations(passage, profil, modele):
    """Extrait des affirmations puis les classe en 5 buckets par ancrage.

    1. retenues                : citation litterale + date ancree proche
                                 OU (personne nommee + verbe d'action + objet numerote)
    2. hors_condition          : citation litterale mais sans date ni objet
                                 identifie -> probablement pas un fait
    3. non_retrouvees          : texte non retrouve dans la page
    4. approximatives          : correspondance approximative (PAS un extrait
                                 exact ; ne peut pas etre presente comme cite)
    5. negation_divergente     : l'affirmation et la page different sur la
                                 negation -> risque d'inversion de sens
    """
    if not _contient_fait_concret(passage["texte"]):
        return {
            "etat": "non_concret",
            "raison": "aucune date ni nombre a deux chiffres detecte",
            "affirmations_retenues": [],
            "affirmations_hors_condition": [],
           "affirmations_non_retrouvees_dans_page": [],
            "affirmations_approximatives": [],
            "affirmations_negation_divergente": [],
            "non_extraites": True,
            "non_concret": True,
            "duree_secondes": 0.0,
        }

    try:
        gbnf = generer_gbnf(SCHEMA_AFFIRMATIONS)
    except SchemaNonSupporte as e:
        return {"etat": "erreur_schema", "raison": str(e), "affirmations": []}

    chemin_gram = _ecrire_grammaire(gbnf)
    try:
        r = executer_llama_completion(
            str(modele),
            PROMPT_AFFIRMATIONS.format(passage=passage["texte"]),
            max_tokens=profil.max_tokens,
            temperature=0.1,
            contexte=profil.contexte,
            n_gpu_layers=profil.n_gpu_layers,
            timeout=120.0,
            grammar_file=chemin_gram,
        )
    finally:
        try:
            os.unlink(chemin_gram)
        except OSError:
            pass

    if not r.ok:
        return {
            "etat": "erreur_modele",
            "raison": (r.erreur or "echec sans message")[:300],
            "affirmations": [],
        }
    if not r.json_parse_valide or not r.json_texte_utilise:
        return {
            "etat": "erreur_json",
            "raison": "reponse non JSON valide",
            "reponse_brute": (r.reponse or "")[:300],
            "affirmations": [],
        }
    try:
        objet = json.loads(r.json_texte_utilise)
    except json.JSONDecodeError as e:
        return {"etat": "erreur_json", "raison": str(e), "affirmations": []}

    validation = valider(r.json_texte_utilise, SCHEMA_AFFIRMATIONS)
    if not validation.schema_technique_valide:
        raison = "; ".join(validation.violations[:5]) if validation.violations else "invalide"
        return {
            "etat": "erreur_validation",
            "raison": raison,
            "affirmations": objet.get("affirmations", []),
        }

    from ancrage import ancrer as _ancrer
    from dedup import dedupliquer as _dedup
    from verbs_action import contient_verbe_action as _verbe
    import re as _re

    texte_page = passage.get("texte", "")
    affirmations_brutes = [_ancrer(a, texte_page) for a in objet.get("affirmations", [])]
    affirmations_brutes = _dedup(affirmations_brutes)

    retenues, hors_cond, non_retrouvees, approximatives, neg_div = [], [], [], [], []

    for aff in affirmations_brutes:
        statut = aff.get("texte_statut", "non_retrouve")
        if statut == "negation_divergente":
            neg_div.append(aff)
            continue
        if statut == "correspondance_approximative":
            approximatives.append(aff)
            continue
        if statut == "non_retrouve" or statut == "vide":
            non_retrouvees.append(aff)
            continue

        pers = (aff.get("personnes") or "").strip().lower()
        personne_nommee = pers not in ("", "aucune", "aucun")
        date_ancree = aff.get("date_statut") == "ancree_proche_extrait"

        if date_ancree and personne_nommee:
            retenues.append(aff)
            continue
        texte_aff = aff.get("texte", "")
        a_numero = bool(_re.search(
            r"dossier[^.]*?\d{2,}|\bnumero\s+\d{2,}",
            texte_aff, _re.IGNORECASE,
        ))
        if personne_nommee and _verbe(texte_aff) and a_numero:
            aff_marquee = dict(aff)
            aff_marquee["concret_sans_date"] = True
            retenues.append(aff_marquee)
            continue
        aff_hc = dict(aff)
        aff_hc["hors_condition"] = True
        hors_cond.append(aff_hc)

    if retenues:
        etat = "ok"
    elif approximatives or neg_div or non_retrouvees:
        etat = "signaux_a_examiner"
    elif not affirmations_brutes:
        etat = "vide"
    else:
        etat = "hors_condition"

    return {
        "etat": etat,
        "affirmations_retenues": retenues,
        "affirmations_hors_condition": hors_cond,
        "affirmations_non_retrouvees_dans_page": non_retrouvees,
        "affirmations_approximatives": approximatives,
        "affirmations_negation_divergente": neg_div,
        "non_extraites": not affirmations_brutes,
        "duree_secondes": r.duree_secondes,
    }




def _mots_significatifs(texte):
    return set(re.findall(r"\b\w{5,}\b", texte.lower()))


def _est_secondaire(affirmation):
    date = (affirmation.get("date") or "").strip().lower()
    pers = (affirmation.get("personnes") or "").strip().lower()
    return date in ("", "inconnue", "inconnu") and pers in ("", "aucune", "aucun")


def rapprocher(affirmation, corpus, *, secondaire=None):
    if secondaire is None:
        secondaire = _est_secondaire(affirmation)
    texte = affirmation.get("texte", "")
    mots_aff = _mots_significatifs(texte)
    if not mots_aff:
        return {"etat": "affirmation_vide", "article": None, "score": 0.0,
                "secondaire": secondaire}

    scores = []
    for article in corpus:
        ref = article.get("titre", "") + " " + article.get("texte", "")
        mots_ref = _mots_significatifs(ref)
        if not mots_ref:
            continue
        communs = mots_aff & mots_ref
        score = len(communs) / len(mots_aff)
        scores.append({"article": article, "score": score,
                       "communs": sorted(communs)})

    scores.sort(key=lambda x: x["score"], reverse=True)
    if not scores:
        return {"etat": "manquant", "article": None, "score": 0.0,
                "raison": "corpus sans mots significatifs",
                "secondaire": secondaire}

    top = scores[0]
    second = scores[1] if len(scores) > 1 else None
    assez_de_mots = len(top["communs"]) >= 2
    score_suffisant = top["score"] >= 0.15
    ecart_ok = (second is None) or (top["score"] - second["score"] >= 0.05)

    if (score_suffisant and assez_de_mots and ecart_ok
            and not secondaire):
        return {
            "etat": "propose",
            "article": {k: top["article"].get(k, "") for k in
                        ("id", "code", "numero", "titre", "version")},
            "score": round(top["score"], 3),
            "communs": top["communs"],
            "motif": "recouvrement lexical " + f"{top['score']:.2f}"
                     + " sur " + str(len(top["communs"])) + " mot(s) : "
                     + ", ".join(top["communs"]),
            "limite": "rapprochement lexical, sans verification semantique",
            "secondaire": secondaire,
        }
    if top["score"] >= 0.05:
        return {
            "etat": "incertain",
            "article": {k: top["article"].get(k, "") for k in
                        ("id", "code", "numero", "titre", "version")},
            "score": round(top["score"], 3),
            "communs": top["communs"],
            "motif": "score faible (" + f"{top['score']:.2f}" + "), "
                     + str(len(top["communs"])) + " mot(s) commun(s) : "
                     + (", ".join(top["communs"]) or "aucun"),
            "limite": "a examiner par l'avocat, pas une proposition ferme",
            "secondaire": secondaire,
        }
    return {
        "etat": "manquant",
        "article": None,
        "score": round(top["score"], 3),
        "raison": "aucun article au-dessus du seuil 0.05 (meilleur : "
                  + f"{top['score']:.2f})",
        "secondaire": secondaire,
    }


def executer_parcours(
    *,
    pdf: Path = PDF_DEFAUT,
    corpus_chemin: Path = CORPUS_DEFAUT,
    modele: Path = MODELE_DEFAUT,
    pages: Optional[list[int]] = None,
) -> dict:
    debut = time.monotonic()
    materiel = detecter_materiel()
    taille_modele = modele.stat().st_size / (1024 ** 3) if modele.is_file() else 2.0
    try:
        profil = choisir_profil(materiel, taille_modele)
    except (MaterielInsuffisant, ConfigurationRefusee) as e:
        return {
            "etat_global": "non_supporte",
            "raison": str(e),
            "materiel": asdict(materiel),
        }

    inventaire = inventaire_pdf(pdf, pages=pages)
    corpus = charger_corpus(corpus_chemin)

    resultats = []
    for passage in inventaire["passages"]:
        extraction = extraire_affirmations(passage, profil, modele)
        rapprochements = [
            {"affirmation": aff, "rapprochement": rapprocher(aff, corpus)}
            for aff in extraction.get("affirmations", [])
        ]
        resultats.append({
            "piece": passage["piece"],
            "page": passage["page"],
            "etat": extraction["etat"],
            "affirmations": extraction.get("affirmations", []),
            "rapprochements": rapprochements,
            "raison": extraction.get("raison"),
            "duree_secondes": extraction.get("duree_secondes"),
        })

    return {
        "etat_global": "ok",
        "materiel": asdict(materiel),
        "profil": asdict(profil),
        "piece": inventaire["piece"],
        "sha_piece": inventaire["sha_piece"],
        "corpus": str(corpus_chemin),
        "modele": str(modele),
        "duree_secondes": round(time.monotonic() - debut, 2),
        "passages": resultats,
    }


if __name__ == "__main__":
    import sys
    pages = [int(x) for x in sys.argv[1:]] or [2]
    r = executer_parcours(pages=pages)
    print(json.dumps(r, ensure_ascii=False, indent=2))
