"""Adaptation d'une référence structurée au résolveur strict Beaume.

Aucun choix permissif : une référence non unique ou sans provenance est rejetée.
Ce module ne déduit pas une référence depuis un visa en texte libre.
"""
from dataclasses import dataclass
from datetime import date
import re

from beaume.legal.model import CodeJuridique
from beaume.legal.normalisation import normaliser_numero
from beaume.ports.resolveur_articles import ResolveurArticles, StatutResolution


class VisaInvalide(ValueError):
    """Référence invalide ou résolution non exploitable."""


class ResolutionAmbigue(VisaInvalide):
    """Aucune famille/version unique ne peut être retenue."""


class VersionNonApplicable(VisaInvalide):
    """Version absente, incohérente ou insuffisamment tracée."""


@dataclass(frozen=True)
class ReferenceVisa:
    code: str
    numero: str
    version_visa: str | None = None


@dataclass(frozen=True)
class ArticleResolu:
    article_id: str
    version_legiarti: str
    code: str
    numero: str


def resoudre_reference(
    depot: ResolveurArticles, ref: ReferenceVisa, date_faits: date,
) -> ArticleResolu:
    """Préserve les verdicts du dépôt, avec conversion explicite du code."""
    try:
        code = CodeJuridique(ref.code)
        numero = normaliser_numero(ref.numero)
    except (ValueError, TypeError) as exc:
        raise VisaInvalide("reference_invalide") from exc
    resolution = depot.resoudre_article(code, numero, date_faits, strict=True)
    if resolution.statut in {
        StatutResolution.AMBIGUITE_FAMILLES,
        StatutResolution.AMBIGUITE_VERSIONS,
        StatutResolution.REFERENCE_ABSENTE,
    }:
        raise ResolutionAmbigue(resolution.statut.value)
    if resolution.statut in {
        StatutResolution.AUCUNE_VERSION_A_LA_DATE,
        StatutResolution.PROVENANCE_INSUFFISANTE,
    }:
        raise VersionNonApplicable(resolution.statut.value)
    if resolution.statut != StatutResolution.UNIQUE:
        raise VisaInvalide(resolution.statut.value)
    famille, version = resolution.article_id_famille, resolution.version_legiarti
    if not famille or not version or not all(
        re.fullmatch(r"LEGIARTI\d{12}", v) for v in (famille, version)
    ):
        raise VersionNonApplicable("identifiant_ou_provenance_manquant")
    if resolution.code != code or resolution.numero_normalise != numero:
        raise VisaInvalide("reference_incoherente")
    if ref.version_visa is not None and ref.version_visa != version:
        raise VersionNonApplicable("version_url_incompatible_date")
    return ArticleResolu(famille, version, code.value, numero)
