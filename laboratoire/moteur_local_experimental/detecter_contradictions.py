"""detecter_contradictions.py — Detection deterministe, niveau d incertitude explicite.

Un numero de dossier commun ne suffit PAS a prouver que deux phrases parlent
du meme objet. On identifie l OBJET de la reception/du transfert et on ne
qualifie de "contradiction" que si l objet est identique. Sinon : "ambigu"
(signal a examiner, pas une certitude).
"""
from __future__ import annotations
import re
import unicodedata

_VERBES_RECEPTION_POS = re.compile(
    r"\b(confirme.*reception|re[cç]oit|a\s+re[cç]u|receptionne)\b",
    re.IGNORECASE,
)
_VERBES_RECEPTION_NEG = re.compile(
    r"\b(ne\s+(?:pas|jamais).*re[cç]u"
    r"|n['\u2019]a\s+(?:pas|jamais).*re[cç]u"
    r"|nie.*re[cç]u|nie.*reception|conteste.*re[cç]u|conteste.*reception"
    r"|dement.*re[cç]u|dement.*reception|jamais\s+re[cç]u|pas\s+re[cç]u)\b",
    re.IGNORECASE,
)
_VERBES_TRANSFERT_POS = re.compile(
    r"\b(remet|a\s+remis|envoie|a\s+envoye|transmet|a\s+transmis)\b",
    re.IGNORECASE,
)

_OBJETS = (
    "dossier", "contrat", "facture", "courrier", "colis", "lettre",
    "email", "courriel", "message", "document", "piece", "bon",
    "cheque", "virement", "mandat", "acte", "notification", "convocation",
)


def _normaliser(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return texte


def _dossiers(texte):
    return set(re.findall(r"dossier[^.]*?(\d{2,})", texte, re.IGNORECASE))


def _objet(texte):
    t = _normaliser(texte)
    return frozenset(o for o in _OBJETS if re.search(r"\b" + o + r"\b", t))


def _objet_de_la_reception(texte):
    """Objet apres 'reception du/de la/des X' ou apres 'recu le/la/les X',
    ou apres 'remet le/la/les X'. Plus precis que d'avaler tous les objets."""
    t = _normaliser(texte)
    for patron in (
        r"reception\s+d[ue]\s+(?:la\s+|le\s+|l['\u2019]|les\s+)?([a-z]+)",
        r"re[cç]u\s+(?:la\s+|le\s+|l['\u2019]|les\s+)?([a-z]+)",
        r"remet\s+(?:la\s+|le\s+|l['\u2019]|les\s+)?([a-z]+)",
        r"envoie\s+(?:la\s+|le\s+|l['\u2019]|les\s+)?([a-z]+)",
        r"transmet\s+(?:la\s+|le\s+|l['\u2019]|les\s+)?([a-z]+)",
    ):
        m = re.search(patron, t)
        if m and m.group(1) in _OBJETS:
            return frozenset([m.group(1)])
    # Repli : si un seul objet present ET que ce n'est pas 'dossier' seul.
    # 'dossier' seul ne dit pas quel objet est recu -> on ne sait pas.
    tous = _objet(texte)
    if len(tous) == 1 and "dossier" not in tous:
        return tous
    return frozenset()


def _polarite(texte):
    pos_r = bool(_VERBES_RECEPTION_POS.search(texte))
    neg_r = bool(_VERBES_RECEPTION_NEG.search(texte))
    if pos_r and not neg_r:
        return "reception_positive"
    if neg_r and not pos_r:
        return "reception_negative"
    if _VERBES_TRANSFERT_POS.search(texte):
        return "transfert_positif"
    return "neutre"


def _comparer(a, b, dossier):
    pa = _polarite(a["texte"])
    pb = _polarite(b["texte"])
    if pa == "neutre" or pb == "neutre" or pa == pb:
        return None

    oa = _objet_de_la_reception(a["texte"])
    ob = _objet_de_la_reception(b["texte"])
    meme_objet = bool(oa) and oa == ob

    base = {
        "dossier": dossier,
        "page_a": a["page"], "page_b": b["page"],
        "texte_a": a["texte"], "texte_b": b["texte"],
        "polarite_a": pa, "polarite_b": pb,
        "objet_a": sorted(oa), "objet_b": sorted(ob),
        "meme_objet": meme_objet,
    }
    paires = {pa, pb}

    if paires == {"reception_positive", "reception_negative"}:
        if meme_objet:
            base["niveau"] = "contradiction"
            base["raison"] = (
                "un document affirme la reception de " + "/".join(sorted(oa))
                + ", un autre la nie (dossier " + dossier + ", meme objet)"
            )
        else:
            base["niveau"] = "ambigu"
            base["raison"] = (
                "reception affirmee vs niee sur le dossier " + dossier
                + ", objets differents ou non identifies : " + str(sorted(oa))
                + " vs " + str(sorted(ob)) + " — a examiner"
            )
        return base

    if paires == {"transfert_positif", "reception_negative"}:
        if meme_objet:
            base["niveau"] = "tension"
            base["raison"] = (
                "un document decrit un transfert de " + "/".join(sorted(oa))
                + ", un autre nie la reception (dossier " + dossier
                + ", meme objet). A examiner : le transfert a-t-il abouti ?"
            )
        else:
            base["niveau"] = "ambigu"
            base["raison"] = (
                "transfert vs non-reception sur le dossier " + dossier
                + ", objets differents ou non identifies : " + str(sorted(oa))
                + " vs " + str(sorted(ob)) + " — a examiner"
            )
        return base
    return None


def detecter_contradictions(affirmations_avec_page):
    par_dossier = {}
    for aff in affirmations_avec_page:
        for d in _dossiers(aff["texte"]):
            par_dossier.setdefault(d, []).append(aff)

    resultats = []
    for dossier, groupe in par_dossier.items():
        for i, a in enumerate(groupe):
            for b in groupe[i + 1:]:
                res = _comparer(a, b, dossier)
                if res is not None:
                    resultats.append(res)
    return resultats
