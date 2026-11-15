"""dedup.py — Dedoublonnage deterministe des affirmations quasi-identiques.

Regle : si le texte normalise d une affirmation est une sous-chaine du texte
normalise d une autre, garder la version la plus longue.
"""
from __future__ import annotations
import re
import unicodedata


def _normaliser(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def dedupliquer(affirmations):
    if not affirmations:
        return []
    resultats = []
    for aff in affirmations:
        texte_a = _normaliser(aff.get("texte", ""))
        remplace = False
        for i, existant in enumerate(resultats):
            texte_b = _normaliser(existant.get("texte", ""))
            if texte_a in texte_b:
                remplace = True
                break
            if texte_b in texte_a:
                resultats[i] = aff
                remplace = True
                break
        if not remplace:
            resultats.append(aff)
    return resultats
