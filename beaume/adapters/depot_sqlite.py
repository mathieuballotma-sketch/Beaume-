"""Adaptateur SQLite : stockage persistant du corpus legal.

Utilise la stdlib sqlite3 + FTS5 pour la recherche plein-texte.
Aucune dependance externe. Aucune connexion reseau.

Le FTS5 est configurer avec 'remove_diacritics 2' pour ignorer les
accents a la recherche (delai = delai, ete = ete, etc.).
"""
import sqlite3
from datetime import date
from pathlib import Path

from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.normalisation import normaliser_numero
from beaume.legal.model import (
    Article,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)
from beaume.ports.depot_articles import ResultatRechercheArticle
from beaume.utils.logging import get_logger

log = get_logger("depot_sqlite")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    numero TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    article_id TEXT NOT NULL,
    numero TEXT NOT NULL,
    date_debut TEXT NOT NULL,
    date_fin TEXT,
    texte TEXT NOT NULL,
    statut TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (article_id, date_debut),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_versions_dates
    ON versions (article_id, date_debut, date_fin);

CREATE INDEX IF NOT EXISTS idx_articles_code_numero
    ON articles (code, numero);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    article_id UNINDEXED,
    code UNINDEXED,
    numero UNINDEXED,
    texte,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


class DepotSQLite:
    """Depot d'articles base sur SQLite + FTS5."""

    def __init__(self, chemin: Path) -> None:
        self.chemin = Path(chemin)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.chemin))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Ecriture
    # ------------------------------------------------------------------

    def enregistrer(self, articles: list[Article]) -> None:
        if not articles:
            return
        curseur = self._conn.cursor()
        for article in articles:
            curseur.execute(
                "INSERT OR REPLACE INTO articles (id, code, numero) "
                "VALUES (?, ?, ?)",
                (
                    article.id.valeur,
                    article.code.value,
                    normaliser_numero(article.numero),
                ),
            )
            # On purge les versions precedentes de cet article
            curseur.execute(
                "DELETE FROM versions WHERE article_id = ?",
                (article.id.valeur,),
            )
            for v in article.versions:
                curseur.execute(
                    "INSERT INTO versions ("
                    "  article_id, numero, date_debut, date_fin, "
                    "  texte, statut, source"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        v.article_id.valeur,
                        normaliser_numero(v.numero),
                        v.date_debut.isoformat(),
                        v.date_fin.isoformat() if v.date_fin else None,
                        v.texte,
                        v.statut.value,
                        v.source,
                    ),
                )
            # On purge la FTS pour cet article
            curseur.execute(
                "DELETE FROM articles_fts WHERE article_id = ?",
                (article.id.valeur,),
            )
            # On reindexe les versions
            for v in article.versions:
                curseur.execute(
                    "INSERT INTO articles_fts "
                    "(article_id, code, numero, texte) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        v.article_id.valeur,
                        article.code.value,
                        v.numero,
                        v.texte,
                    ),
                )
        self._conn.commit()
        log.info("Enregistre %d articles dans le depot", len(articles))

    def vider(self) -> None:
        curseur = self._conn.cursor()
        curseur.execute("DELETE FROM articles")
        curseur.execute("DELETE FROM versions")
        curseur.execute("DELETE FROM articles_fts")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def compter(self) -> int:
        (n,) = self._conn.execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()
        return int(n)

    def trouver(
        self,
        code: CodeJuridique,
        numero: str,
        date_reference: date,
    ) -> tuple[Article, VersionArticle] | None:
        iso = date_reference.isoformat()
        numero = normaliser_numero(numero)
        ligne = self._conn.execute(
            """
            SELECT a.id AS article_id, a.code AS code, a.numero AS numero,
                   v.date_debut, v.date_fin, v.texte, v.statut, v.source
            FROM articles a
            JOIN versions v ON v.article_id = a.id
            WHERE a.code = ?
              AND v.numero = ?
              AND v.date_debut <= ?
              AND (v.date_fin IS NULL OR v.date_fin >= ?)
            ORDER BY v.date_debut DESC
            LIMIT 1
            """,
            (code.value, numero, iso, iso),
        ).fetchone()

        if ligne is None:
            return None

        # Charge toutes les versions de cet article pour reconstruire l'Article.
        versions_rows = self._conn.execute(
            "SELECT numero, date_debut, date_fin, texte, statut, source "
            "FROM versions WHERE article_id = ? ORDER BY date_debut",
            (ligne["article_id"],),
        ).fetchall()

        versions = [
            VersionArticle(
                article_id=IdentifiantLegifrance(valeur=ligne["article_id"]),
                numero=r["numero"],
                date_debut=date.fromisoformat(r["date_debut"]),
                date_fin=(
                    date.fromisoformat(r["date_fin"]) if r["date_fin"] else None
                ),
                texte=r["texte"],
                statut=StatutVersion(r["statut"]),
                source=r["source"],
            )
            for r in versions_rows
        ]

        article = Article(
            id=IdentifiantLegifrance(valeur=ligne["article_id"]),
            code=CodeJuridique(ligne["code"]),
            numero=ligne["numero"],
            versions=versions,
        )

        version_trouvee = next(
            v for v in versions
            if v.date_debut <= date_reference
            and (v.date_fin is None or v.date_fin >= date_reference)
        )

        return article, version_trouvee

    def trouver_par_id(
        self,
        article_id: str,
        date_reference: date,
    ) -> Article | None:
        """Retrouve un Article complet par son identifiant."""
        ligne = self._conn.execute(
            "SELECT id, code, numero FROM articles WHERE id = ?",
            (article_id,),
        ).fetchone()
        if ligne is None:
            return None

        versions_rows = self._conn.execute(
            "SELECT numero, date_debut, date_fin, texte, statut, source "
            "FROM versions WHERE article_id = ? ORDER BY date_debut",
            (article_id,),
        ).fetchall()

        versions = [
            VersionArticle(
                article_id=IdentifiantLegifrance(valeur=article_id),
                numero=r["numero"],
                date_debut=date.fromisoformat(r["date_debut"]),
                date_fin=(
                    date.fromisoformat(r["date_fin"]) if r["date_fin"] else None
                ),
                texte=r["texte"],
                statut=StatutVersion(r["statut"]),
                source=r["source"],
            )
            for r in versions_rows
        ]

        return Article(
            id=IdentifiantLegifrance(valeur=ligne["id"]),
            code=CodeJuridique(ligne["code"]),
            numero=ligne["numero"],
            versions=versions,
        )

    def rechercher_texte(
        self,
        mots: str,
        limite: int = 10,
    ) -> list[ResultatRechercheArticle]:
        mots = (mots or "").strip()
        if not mots:
            return []
        if limite <= 0:
            raise ValueError("limite doit etre > 0")

        lignes = self._conn.execute(
            """
            SELECT article_id,
                   code,
                   numero,
                   bm25(articles_fts) AS score,
                   snippet(articles_fts, 3, '[', ']', '...', 20) AS extrait
            FROM articles_fts
            WHERE articles_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (mots, limite),
        ).fetchall()

        return [
            ResultatRechercheArticle(
                article_id=r["article_id"],
                code=r["code"],
                numero=r["numero"],
                extrait=r["extrait"],
                # bm25 retourne un score plus petit = plus pertinent.
                # On inverse le signe pour que grand = meilleur.
                score=-float(r["score"]),
            )
            for r in lignes
        ]