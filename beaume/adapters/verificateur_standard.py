"""Adaptateur standard du verificateur de citations.

Confronte une Citation au corpus legal. Depuis la refonte du
2026-10-19, la Citation est hydratee par l'application (code, numero,
extrait viennent de SQLite, pas du LLM). Le verificateur reste la
derniere barriere : il verifie l'existence de l'article, la version
applicable a la date, la lisibilite du statut et la coherence de l'extrait.

Regles strictes :
  - Numero absent            -> NUMERO_MANQUANT
  - Article absent           -> INTROUVABLE
  - Aucune version a la date -> VERSION_INCORRECTE
  - Statut source inconnu   -> STATUT_VERSION_INCONNU
  - Extrait non present      -> EXTRAIT_MANQUANT
  - Extrait different        -> TEXTE_DIFFERENT
  - Sinon                    -> VALIDE

Le statut ABROGE de la source ne rejette pas a lui seul une version
historique : si ses dates encadrent la date de reference, elle peut
etre la version applicable a cette date. S'il manque la date de fin
d'une version marquee ABROGE, le corpus est insuffisant pour conclure.
"""
import re
import unicodedata

from beaume.legal.model import (
    Citation,
    ResultatVerification,
    StatutVerification,
    StatutVersion,
)
from beaume.legal.normalisation import normaliser_numero
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
        if not citation.numero.strip():
            return ResultatVerification(
                statut=StatutVerification.NUMERO_MANQUANT,
                citation=citation,
                message="Numero d'article absent : reference incomplete.",
            )

        if citation.article_id:
            article = self.depot.trouver_par_id(
                citation.article_id, citation.date_reference,
            )
            if article is None:
                return ResultatVerification(
                    statut=StatutVerification.INTROUVABLE,
                    citation=citation,
                    message="Identifiant d'article introuvable dans le corpus.",
                )
            version = article.version_a(citation.date_reference)
            if version is None:
                return ResultatVerification(
                    statut=StatutVerification.VERSION_INCORRECTE,
                    citation=citation,
                    message="Article connu mais aucune version a cette date.",
                )
            if (
                article.code != citation.code
                or normaliser_numero(version.numero)
                != normaliser_numero(citation.numero)
            ):
                return ResultatVerification(
                    statut=StatutVerification.IDENTIFIANT_INCOHERENT,
                    citation=citation,
                    message=(
                        "Le code ou le numero ne correspond pas a "
                        "l'identifiant d'article."
                    ),
                )
            res = (article, version)
        else:
            res = self.depot.trouver(
                citation.code, citation.numero, citation.date_reference,
            )

        if res is None:
            if self.depot.article_existe(citation.code, citation.numero):
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

        if version.statut == StatutVersion.INCONNU:
            return ResultatVerification(
                statut=StatutVerification.STATUT_VERSION_INCONNU,
                citation=citation,
                version=version,
                message=(
                    "Le statut de cette version est inconnu dans le corpus; "
                    "la citation ne peut pas etre validee automatiquement."
                ),
            )

        if version.statut == StatutVersion.ABROGE and version.date_fin is None:
            return ResultatVerification(
                statut=StatutVerification.VERSION_INCORRECTE,
                citation=citation,
                version=version,
                message=(
                    "Version marquee abrogee mais sans date de fin; "
                    "sa periode d'applicabilite n'est pas verifiable."
                ),
            )

        if not citation.extrait or not citation.extrait.strip():
            return ResultatVerification(
                statut=StatutVerification.EXTRAIT_MANQUANT,
                citation=citation,
                version=version,
                message="Aucun extrait fourni : citation non verifiable.",
            )

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
