"""ancrage.py — Trois niveaux d'ancrage du texte + ancrage date avec proximité.

Niveaux de texte :
- citation_litterale      : la phrase (normalisée espaces) est verbatim dans la page
- correspondance_approximative : forte similarité mais PAS exacte (reformulation,
  ordre, mots) — ne doit pas être présentée comme un extrait exact
- negation_divergente    : l'aff contient une négation absente de la fenêtre de
  page correspondante (ou inversement)
- non_retrouve           : aucune correspondance plausible

Pour la date :
- inconnue                       : pas de date dans l'affirmation
- non_ancree_dans_affirmation    : date proposée par le modèle, absente de l'aff
- non_ancree_dans_page           : date absente du texte de la page
- ancree_proche_extrait          : date dans la page ET proche de l'extrait
- date_presente_ailleurs_dans_page : date présente mais éloignée de l'extrait —
  l'association n'est pas prouvée
"""
from __future__ import annotations
import difflib
import re
import unicodedata

_NEGATIONS = re.compile(
    r"\b(ne|n['\u2019]|pas|jamais|aucun|aucune|rien|nullement|point)\b",
    re.IGNORECASE,
)

_MOIS_INDEX = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "décembre": 12,
}

SEUIL_APPROX = 0.6
SEUIL_PROXIMITE_CAR = 200


def normaliser_espaces(texte):
    if not texte:
        return ""
    return re.sub(r"\s+", " ", texte).strip()


def _normaliser_pour_similarite(texte):
    t = (texte or "").lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _formes_litterales(date_iso):
    try:
        annee, mois, jour = date_iso.split("-")
        annee_i, mois_i, jour_i = int(annee), int(mois), int(jour)
    except (ValueError, AttributeError):
        return []
    formes = [date_iso]
    formes.append(format(jour_i, "02d") + "/" + format(mois_i, "02d") + "/" + annee)
    formes.append(format(jour_i, "02d") + "-" + format(mois_i, "02d") + "-" + annee)
    formes.append(format(jour_i, "02d") + "." + format(mois_i, "02d") + "." + annee)
    formes.append(format(jour_i, "d") + "." + format(mois_i, "02d") + "." + annee)
    for nom_mois, index in _MOIS_INDEX.items():
        if index == mois_i:
            formes.append(format(jour_i, "d") + " " + nom_mois + " " + annee)
            if jour_i == 1:
                formes.append("1er " + nom_mois + " " + annee)
    return formes


def _nb_negations(texte):
    return len(_NEGATIONS.findall(texte or ""))


_MOTS_VIDES = frozenset({
    "le", "la", "les", "un", "une", "des", "du", "de", "au", "aux",
    "et", "ou", "en", "sur", "sous", "avec", "sans", "par", "pour",
    "est", "sont", "a", "ont", "que", "qui", "ce", "cette", "ces",
    "il", "elle", "ils", "elles", "dans", "se", "sa", "son", "ses",
    "the", "of", "and", "to", "for", "with", "by", "on", "in",
})


def _mots_distinctifs(texte):
    t = (texte or "").lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    mots = re.findall(r"[a-z0-9]{4,}", t)
    return set(m for m in mots if m not in _MOTS_VIDES)


def _couverture_mots(texte_aff, texte_page):
    """Fraction des mots distinctifs de l'aff trouves dans la page."""
    m_aff = _mots_distinctifs(texte_aff)
    if not m_aff:
        return 0.0
    m_page = _mots_distinctifs(texte_page)
    return len(m_aff & m_page) / len(m_aff)


def _fenetre_autour_de(texte_page, texte_aff, marge=120):
    """Fenetre de la page autour du premier mot distinctif de l'aff."""
    if not texte_page or not texte_aff:
        return texte_page or ""
    tp = normaliser_espaces(texte_page)
    mots = sorted(_mots_distinctifs(texte_aff), key=len, reverse=True)
    for mot in mots:
        idx = tp.lower().find(mot)
        if idx >= 0:
            debut = max(0, idx - marge)
            fin = min(len(tp), idx + len(texte_aff) + marge)
            return tp[debut:fin]
    return tp


def _classifier_texte(texte_aff, texte_page):
    """Retourne (statut, ratio, raison)."""
    ta = normaliser_espaces(texte_aff)
    tp = normaliser_espaces(texte_page)
    if not ta:
        return ("vide", 0.0, "affirmation vide")
    if not tp:
        return ("non_retrouve", 0.0, "page vide")

    # 1) Citation littérale
    if ta in tp:
        return ("citation_litterale", 1.0, "phrase verbatim dans la page")

    # 2) Négation inversée : on regarde la fenêtre la plus probable
    fenetre = _fenetre_autour_de(tp, ta)
    n_aff = _nb_negations(ta)
    n_win = _nb_negations(fenetre)
    if (n_aff == 0 and n_win > 0) or (n_aff > 0 and n_win == 0):
        return (
            "negation_divergente", 0.0,
            "l'affirmation contient " + str(n_aff) + " marqueur(s) de negation, "
            "la fenetre de page en contient " + str(n_win),
        )

    # 3) Correspondance approximative — couverture des mots distinctifs
    ratio = _couverture_mots(ta, fenetre)
    if ratio >= SEUIL_APPROX:
        return (
            "correspondance_approximative", round(ratio, 3),
            "couverture " + str(round(ratio, 3)) + " des mots distinctifs — pas un extrait exact",
        )

    return ("non_retrouve", round(ratio, 3), "mots distinctifs trop peu presents dans la page")


def _position_date(texte_page, date_iso):
    tp_norm = normaliser_espaces(texte_page).lower()
    for forme in _formes_litterales(date_iso):
        idx = tp_norm.find(forme.lower())
        if idx >= 0:
            return idx
    return None


def _position_extrait(texte_page, texte_aff):
    """Retourne la position de la correspondance la PLUS LONGUE dans la page.

    Exclut les motifs qui ne comportent pas au moins 2 mots distinctifs,
    pour ne pas retomber sur le simple prefixe date ('le 3 avril 2024').
    """
    tp_norm = normaliser_espaces(texte_page).lower()
    ta_norm = normaliser_espaces(texte_aff).lower()
    if not ta_norm or not tp_norm:
        return None
    idx = tp_norm.find(ta_norm)
    if idx >= 0:
        return idx
    mots = ta_norm.split()
    for taille in range(len(mots) - 1, 2, -1):
        for debut in range(len(mots) - taille + 1):
            motif = " ".join(mots[debut:debut + taille])
            if len(_mots_distinctifs(motif)) < 2:
                continue
            idx = tp_norm.find(motif)
            if idx >= 0:
                return idx
    return None


def _classifier_date(affirmation, texte_page):
    date = affirmation.get("date", "")
    if not date or date in ("inconnue", "inconnu", ""):
        return {"date_statut": "inconnue"}

    ta = normaliser_espaces(affirmation.get("texte", "")).lower()
    date_dans_aff = any(f.lower() in ta for f in _formes_litterales(date))
    if not date_dans_aff:
        return {
            "date_statut": "non_ancree_dans_affirmation",
            "date_proposee_modele": date,
            "date_effective": "inconnue",
        }

    pos_date = _position_date(texte_page, date)
    if pos_date is None:
        return {
            "date_statut": "non_ancree_dans_page",
            "date_proposee_modele": date,
            "date_effective": "inconnue",
        }

    pos_ext = _position_extrait(texte_page, affirmation.get("texte", ""))
    if pos_ext is None:
        return {
            "date_statut": "date_presente_dans_page_sans_position_extrait",
            "date_effective": date,
            "date_association_verifiee": False,
        }

    distance = abs(pos_date - pos_ext)
    if distance <= SEUIL_PROXIMITE_CAR:
        return {
            "date_statut": "ancree_proche_extrait",
            "date_effective": date,
            "date_association_verifiee": True,
            "distance_caracteres": distance,
        }
    return {
        "date_statut": "date_presente_ailleurs_dans_page",
        "date_effective": date,
        "date_association_verifiee": False,
        "distance_caracteres": distance,
    }


def ancrer(affirmation, texte_page):
    a = dict(affirmation)
    statut, ratio, raison = _classifier_texte(a.get("texte", ""), texte_page)
    a["texte_statut"] = statut
    a["texte_retrouve_dans_page"] = (statut == "citation_litterale")
    a["texte_ratio"] = ratio
    a["texte_raison"] = raison

    date_info = _classifier_date(a, texte_page)
    a.update(date_info)

    if date_info.get("date_effective") is not None:
        a["date"] = date_info["date_effective"]
    return a


def ancrer_liste(affirmations, texte_page):
    return [ancrer(a, texte_page) for a in affirmations]
