"""Adaptateur SQLite : stockage persistant du corpus legal.

Utilise la stdlib sqlite3 + FTS5 pour la recherche plein-texte.
Aucune dependance externe. Aucune connexion reseau.

Le FTS5 est configurer avec 'remove_diacritics 2' pour ignorer les
accents a la recherche (delai = delai, ete = ete, etc.).
"""
import re
import sqlite3
from collections import defaultdict
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
from beaume.ports.resolveur_articles import (
    ResolutionArticle,
    StatutResolution,
)
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


_SENTINELLES_DATE_FIN = frozenset({"2999-01-01", "2222-02-22"})
_LEGIARTI_RE = re.compile(r"(LEGIARTI\d{12})", re.I)


def _extraire_legiarti_depuis_source(source: str | None) -> str | None:
    """Extrait le LEGIARTI d'une source DILA-LEGI unique.

    Retourne None si absent, vide, ou ambigu (plusieurs LEGIARTI).
    Ne devine pas : une source sans LEGIARTI unique est une provenance
    insuffisante, pas une erreur technique.
    """
    if not source:
        return None
    matches = _LEGIARTI_RE.findall(source)
    if len(matches) != 1:
        return None
    return matches[0].upper()


def _version_est_applicable_a(
    date_debut: str,
    date_fin: str | None,
    iso_reference: str,
) -> bool:
    """Vrai si la version couvre date_reference, bornes inclusives.

    Les sentinelles 2999-01-01 et 2222-02-22 sont traitees comme une
    date de fin infinie, conformement a source_dila.py.
    """
    if not date_debut or date_debut > iso_reference:
        return False
    if not date_fin or date_fin in _SENTINELLES_DATE_FIN:
        return True
    return date_fin >= iso_reference


class DepotSQLite:
    """Depot d'articles base sur SQLite + FTS5."""

    def __init__(self, chemin: Path, *, lecture_seule: bool = False) -> None:
        self.chemin = Path(chemin)
        if lecture_seule:
            if not self.chemin.is_file():
                raise FileNotFoundError(self.chemin)
            uri = f"{self.chemin.resolve().as_uri()}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.execute("PRAGMA query_only = ON")
        else:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.chemin))
        self._conn.row_factory = sqlite3.Row
        if not lecture_seule:
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
            curseur.execute(
                "DELETE FROM articles_fts WHERE article_id = ?",
                (article.id.valeur,),
            )
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

        date_debut_selectionnee = date.fromisoformat(ligne["date_debut"])
        version_trouvee = next(
            (
                version for version in versions
                if version.date_debut == date_debut_selectionnee
            ),
            None,
        )
        if version_trouvee is None:
            return None
        return article, version_trouvee

    def article_existe(
        self,
        code: CodeJuridique,
        numero: str,
    ) -> bool:
        """Indique si le corpus connaît une version quelconque de l'article."""
        ligne = self._conn.execute(
            """
            SELECT 1
            FROM articles a
            JOIN versions v ON v.article_id = a.id
            WHERE a.code = ? AND v.numero = ?
            LIMIT 1
            """,
            (code.value, normaliser_numero(numero)),
        ).fetchone()
        return ligne is not None

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
                score=-float(r["score"]),
            )
            for r in lignes
        ]

    # ------------------------------------------------------------------
    # Resolution stricte
    # ------------------------------------------------------------------

    def resoudre_article(
        self,
        code: CodeJuridique,
        numero: str,
        date_reference: date,
        *,
        strict: bool = True,
    ) -> ResolutionArticle:
        """Resolution stricte d'une reference (code, numero, date).

        Ne devine jamais. Voir beaume/ports/resolveur_articles.py pour
        le contrat et la table de decision.

        La recherche porte sur versions.numero (numero historique), et
        non sur articles.numero, comme trouver(). Les bornes de dates
        sont inclusives. Les sentinelles 2999-01-01 et 2222-02-22 sont
        traitees comme date_fin infinie.

        Le parametre strict controle uniquement la richesse du
        diagnostic (candidats renseignes ou non). Il n'existe aucun
        mode permissif : une resolution non unique n'est jamais
        retournee comme si elle l'etait.
        """
        if not isinstance(numero, str) or not numero.strip():
            return ResolutionArticle(
                statut=StatutResolution.DONNEES_INCOHERENTES,
                message="numero_vide",
            )
        try:
            numero_normalise = normaliser_numero(numero)
        except (TypeError, ValueError) as exc:
            return ResolutionArticle(
                statut=StatutResolution.DONNEES_INCOHERENTES,
                message=f"numero_invalide:{type(exc).__name__}",
            )
        if not numero_normalise:
            return ResolutionArticle(
                statut=StatutResolution.DONNEES_INCOHERENTES,
                message="numero_vide_apres_normalisation",
            )
        if not isinstance(date_reference, date):
            return ResolutionArticle(
                statut=StatutResolution.DONNEES_INCOHERENTES,
                message="date_reference_invalide",
            )
        try:
            code_valeur = code.value
        except AttributeError:
            return ResolutionArticle(
                statut=StatutResolution.DONNEES_INCOHERENTES,
                message="code_invalide",
            )

        iso = date_reference.isoformat()

        try:
            rows = self._conn.execute(
                """
                SELECT a.id AS article_id_famille,
                       v.date_debut, v.date_fin, v.statut, v.source
                FROM articles a
                JOIN versions v ON v.article_id = a.id
                WHERE a.code = ? AND v.numero = ?
                ORDER BY a.id, v.date_debut
                """,
                (code_valeur, numero_normalise),
            ).fetchall()
        except sqlite3.Error as exc:
            return ResolutionArticle(
                statut=StatutResolution.ERREUR_TECHNIQUE,
                message=f"sqlite:{type(exc).__name__}",
            )

        if not rows:
            return ResolutionArticle(
                statut=StatutResolution.REFERENCE_ABSENTE,
            )

        familles: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for r in rows:
            familles[r["article_id_famille"]].append(r)

        applicables: dict[str, list[sqlite3.Row]] = {}
        for fam_id, versions in familles.items():
            apps = [
                v for v in versions
                if _version_est_applicable_a(
                    v["date_debut"], v["date_fin"], iso,
                )
            ]
            if apps:
                applicables[fam_id] = apps

        if not applicables:
            return ResolutionArticle(
                statut=StatutResolution.AUCUNE_VERSION_A_LA_DATE,
            )

        if len(applicables) > 1:
            candidats = (
                tuple(sorted(applicables.keys()))
                if not strict else ()
            )
            return ResolutionArticle(
                statut=StatutResolution.AMBIGUITE_FAMILLES,
                candidats=candidats,
                message=f"{len(applicables)} familles applicables",
            )

        fam_id = next(iter(applicables))
        apps = applicables[fam_id]

        if len(apps) > 1:
            candidats = ()
            if not strict:
                candidats = tuple(
                    f"{v['date_debut']}/"
                    f"{_extraire_legiarti_depuis_source(v['source']) or 'NA'}"
                    for v in apps
                )
            return ResolutionArticle(
                statut=StatutResolution.AMBIGUITE_VERSIONS,
                article_id_famille=fam_id,
                candidats=candidats,
                message=f"{len(apps)} versions applicables",
            )

        v = apps[0]
        date_debut = date.fromisoformat(v["date_debut"])
        statut_brut = v["statut"]
        statut_version = getattr(statut_brut, "value", statut_brut)
        if statut_version in ("inconnu", "futur"):
            return ResolutionArticle(
                statut=StatutResolution.PROVENANCE_INSUFFISANTE,
                article_id_famille=fam_id,
                version_date_debut=date_debut,
                code=code,
                numero_normalise=numero_normalise,
                message=f"statut_version_{statut_version}",
            )

        legiarti = _extraire_legiarti_depuis_source(v["source"])
        if not legiarti:
            return ResolutionArticle(
                statut=StatutResolution.PROVENANCE_INSUFFISANTE,
                article_id_famille=fam_id,
                version_date_debut=date_debut,
                code=code,
                numero_normalise=numero_normalise,
                message="source_sans_legiarti_unique",
            )

        return ResolutionArticle(
            statut=StatutResolution.UNIQUE,
            article_id_famille=fam_id,
            version_date_debut=date_debut,
            version_legiarti=legiarti,
            code=code,
            numero_normalise=numero_normalise,
        )
