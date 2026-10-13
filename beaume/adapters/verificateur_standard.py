"""Adaptateur standard du verificateur de citations.

Confronte une Citation produite par le LLM au corpus legal.
Regles strictes :
  - Article absent          -> INTROUVABLE
  - Aucune version a la date -> VERSION_INCORRECTE
  - Article abroge          -> ABROGE
  - Extrait non present     -> TEXTE_DIFFERENT
  - Sinon                   -> VALIDE

La comparaison d'extrait est insensible aux accents, a la casse et
aux espaces multiples, mais elle est STRICTE sur le contenu.
"""
import re
import unicodedata

from beaume.legal.model import (
    Citation,
    ResultatVerification,
    StatutVerification,
    StatutVersion,
)
from beaume.ports.depot_articles import DepotArticles
from beaume.utils.logging import get_logger

log = get_logger("verificateur")


def _normaliser(texte: str) -> str:
    """Normalise un texte pour comparaison : minuscules, sans accents,
    ponctuation -> espaces, espaces multiples -> 1 espace."""
    if not texte:
        return ""
    t = texte.lower()
    t = "".join(
        c for c in unicodedata.normalize("NFD", t)
        if unicodedata.category(c) != "Mn"
    )
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class VerificateurStandard:
    """Verificateur de citations base sur le DepotArticles."""

    def __init__(self, depot: DepotArticles) -> None:
        self.depot = depot

    def verifier(self, citation: Citation) -> ResultatVerification:
        res = self.depot.trouver(
            citation.code, citation.numero, citation.date_reference,
        )

        if res is None:
            # Deux cas : article totalement absent, ou article present
            # mais aucune version a la date. On distingue pour la
            # tracabilite : si l'article existe a une autre date,
            # c'est VERSION_INCORRECTE, sinon INTROUVABLE.
            existe_autre_date = self._article_existe_a_une_autre_date(citation)
            if existe_autre_date:
                return ResultatVerification(
                    statut=StatutVerification.VERSION_INCORRECTE,
                    citation=citation,
                    message="Article connu mais aucune version a cette date.",
                )
            return ResultatVerification(
                statut=StatutVerification.INTROUVABLE,
                citation=citation,
                message="Article introuvable dans le corpus.",
            )

        article, version = res

        if version.statut == StatutVersion.ABROGE:
            return ResultatVerification(
                statut=StatutVerification.ABROGE,
                citation=citation,
                version=version,
                message="Article abroge a cette date.",
            )

        if not citation.extrait or not citation.extrait.strip():
            return ResultatVerification(
                statut=StatutVerification.EXTRAIT_MANQUANT,
                citation=citation,
                version=version,
                message="Aucun extrait fourni : citation non verifiable.",
            )

        if citation.extrait:
            extrait_norm = _normaliser(citation.extrait)
            texte_norm = _normaliser(version.texte)
            if extrait_norm and extrait_norm not in texte_norm:
                return ResultatVerification(
                    statut=StatutVerification.TEXTE_DIFFERENT,
                    citation=citation,
                    version=version,
                    message="L'extrait cite ne figure pas dans le texte officiel.",
                )

        return ResultatVerification(
            statut=StatutVerification.VALIDE,
            citation=citation,
            version=version,
            message="",
        )

    def verifier_toutes(
        self, citations: list[Citation]
    ) -> list[ResultatVerification]:
        return [self.verifier(c) for c in citations]

    def _article_existe_a_une_autre_date(self, citation: Citation) -> bool:
        """Verifie si l'article existe a une autre date quelconque.

        Utilise une date tres ancienne et une date tres lointaine pour
        balayer toutes les versions possibles.
        """
        from datetime import date
        tres_ancien = date(1900, 1, 1)
        tres_futur = date(2100, 1, 1)
        for d in (tres_ancien, tres_futur):
            if self.depot.trouver(citation.code, citation.numero, d):
                return True
        return False
