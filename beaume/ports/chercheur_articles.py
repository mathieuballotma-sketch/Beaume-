"""Port : contrat d'un chercheur d'articles pertinents.

Prend un texte (chunk d'un dossier client) et retourne les articles
du corpus legal les plus pertinents.

Le port ne connait AUCUNE methode de recherche (FTS5, vectoriel, hybride).
"""
from typing import Protocol, runtime_checkable

from beaume.ports.depot_articles import ResultatRechercheArticle


@runtime_checkable
class ChercheurArticles(Protocol):
    def chercher(
        self,
        texte: str,
        limite: int = 5,
    ) -> list[ResultatRechercheArticle]: ...
