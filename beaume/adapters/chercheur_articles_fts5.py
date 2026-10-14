"""Adaptateur : cherche des articles via FTS5 (DepotSQLite).

Respecte le contrat ChercheurArticles.
Extrait les mots-cles du texte, interroge FTS5 en OR, retourne les top N.

Un texte long (chunk de 600 car.) est filtre par mots-cles pour ne pas
noyer la recherche dans du bruit.
"""
from beaume.ports.depot_articles import (
    DepotArticles,
    ResultatRechercheArticle,
)
from beaume.utils.texte import extraire_mots_cles


class ChercheurArticlesFTS5:
    """Chercheur d'articles base sur FTS5 (DepotSQLite)."""

    def __init__(
        self,
        depot: DepotArticles,
        max_mots_cles: int = 200,
    ) -> None:
        self.depot = depot
        self.max_mots_cles = max_mots_cles

    def chercher(
        self,
        texte: str,
        limite: int = 5,
    ) -> list[ResultatRechercheArticle]:
        if limite <= 0:
            raise ValueError("limite doit etre > 0")
        if not texte or not texte.strip():
            return []

        mots = extraire_mots_cles(texte, limite=self.max_mots_cles)
        if not mots:
            return []

        # FTS5 avec OR : on veut les articles qui matchent AU MOINS
        # un mot-cle, pas tous (sinon c'est trop restrictif).
        requete = " OR ".join(mots)
        return self.depot.rechercher_texte(requete, limite=limite)
