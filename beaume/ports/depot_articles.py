"""Port : contrat d'un depot d'articles de loi.

Un depot sait :
- enregistrer des articles,
- retrouver la version en vigueur a une date,
- chercher par mots-cles (plein-texte),
- compter et vider.

Le port ne connait AUCUNE technologie de stockage concrete.
"""
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from beaume.legal.model import Article, CodeJuridique, VersionArticle


@dataclass(frozen=True)
class ResultatRechercheArticle:
    """Un resultat de recherche plein-texte dans le corpus."""
    article_id: str
    code: str
    numero: str
    extrait: str
    score: float


@runtime_checkable
class DepotArticles(Protocol):
    def enregistrer(self, articles: list[Article]) -> None: ...

    def trouver(
        self,
        code: CodeJuridique,
        numero: str,
        date_reference: date,
    ) -> tuple[Article, VersionArticle] | None: ...

    def article_existe(
        self,
        code: CodeJuridique,
        numero: str,
    ) -> bool: ...

    def trouver_par_id(
        self,
        article_id: str,
        date_reference: date,
    ) -> Article | None: ...

    def rechercher_texte(
        self,
        mots: str,
        limite: int = 10,
    ) -> list[ResultatRechercheArticle]: ...

    def compter(self) -> int: ...

    def vider(self) -> None: ...
