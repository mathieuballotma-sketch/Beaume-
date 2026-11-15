"""verbs_action.py — Verbs d action concrets pour le post-filtre.

Liste fermee, deterministe. Sert a retenir un fait non date (personne nommee
+ verbe) plutot que de le jeter en hors_condition.
"""
from __future__ import annotations
import re
import unicodedata

_VERBES = (
    "affirme", "affirmee", "nie", "confirme", "remet", "remise",
    "envoie", "envoye", "recoit", "recu", "receptionne", "demande",
    "conteste", "dement", "declare", "soutient", "reconnait", "admet",
    "contredit", "notifie", "avise", "informe", "refuse", "accepte",
)

def _normaliser(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return texte

_PATTERN = re.compile(r"\b(" + "|".join(_VERBES) + r")\b", re.IGNORECASE)

def contient_verbe_action(texte):
    return bool(_PATTERN.search(_normaliser(texte)))
