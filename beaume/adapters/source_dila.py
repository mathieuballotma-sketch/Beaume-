"""Adaptateur de lecture du corpus DILA LEGI v2.

Lit la base SQLite produite par `scripts/preparer_legi_dila.py` (Codex)
et expose les articles avec toutes leurs versions, au format attendu
par `DepotSQLite.enregistrer()`.

Source : vue `versions_articles_sans_conflit_source`, qui exclut les
identifiants aux copies divergentes. Les textes non codifiés (code NULL)
sont ignorés : ils ne correspondent à aucun `CodeJuridique` de Beaume.

Correctifs du 2026-10-20 :

1. `VersionArticle.article_id` doit être le famille_id (partagé par toutes
   les versions d'un même article), pas le LEGIARTI propre à chaque
   version. Sinon `versions.article_id` ne rejoint jamais `articles.id`.

2. La PRIMARY KEY de `versions` est `(article_id, date_debut)`. Deux
   LEGIARTI de la même famille peuvent partager une date_debut (renumé-
   rotation, republication DILA, réutilisation de numéro). On dédoublonne
   par date_debut, en gardant la version la plus informative.

Le LEGIARTI propre à chaque version est conservé dans `source`, pour
permettre de remonter au XML DILA original.

Licence : DILA — Légifrance, base LEGI, Licence Ouverte 2.0.
Attribution obligatoire dans toute sortie.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterator

from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)
from beaume.utils.logging import get_logger

log = get_logger("source_dila")


# Mapping LEGITEXT → CodeJuridique de Beaume.
_LEGITEXT_VERS_CODE: dict[str, CodeJuridique] = {
    "LEGITEXT000006070721": CodeJuridique.CODE_CIVIL,
    "LEGITEXT000006070719": CodeJuridique.CODE_PENAL,
    "LEGITEXT000006072050": CodeJuridique.CODE_TRAVAIL,
    "LEGITEXT000005634379": CodeJuridique.CODE_COMMERCE,
    "LEGITEXT000006069565": CodeJuridique.CODE_CONSOMMATION,
    "LEGITEXT000006073189": CodeJuridique.CODE_SECURITE_SOCIALE,
    "LEGITEXT000006070716": CodeJuridique.CODE_PROCEDURE_CIVILE,
    "LEGITEXT000006071154": CodeJuridique.CODE_PROCEDURE_PENALE,
    "LEGITEXT000006072665": CodeJuridique.CODE_SANTE_PUBLIQUE,
    "LEGITEXT000006071367": CodeJuridique.CODE_RURAL,
    "LEGITEXT000023086525": CodeJuridique.CODE_TRANSPORTS,
    "LEGITEXT000006074220": CodeJuridique.CODE_ENVIRONNEMENT,
    "LEGITEXT000006070633": CodeJuridique.CODE_COLLECTIVITES_TERRITORIALES,
    "LEGITEXT000006072026": CodeJuridique.CODE_MONETAIRE_FINANCIER,
    "LEGITEXT000006071191": CodeJuridique.CODE_EDUCATION,
    "LEGITEXT000006074096": CodeJuridique.CODE_CONSTRUCTION_HABITATION,
    "LEGITEXT000006074069": CodeJuridique.CODE_ACTION_SOCIALE_FAMILLES,
    "LEGITEXT000006071307": CodeJuridique.CODE_DEFENSE,
    "LEGITEXT000044416551": CodeJuridique.CODE_FONCTION_PUBLIQUE,
    "LEGITEXT000023983208": CodeJuridique.CODE_ENERGIE,
    "LEGITEXT000025503132": CodeJuridique.CODE_SECURITE_INTERIEURE,
    "LEGITEXT000006070158": CodeJuridique.CODE_ETRANGERS,
    "LEGITEXT000006074075": CodeJuridique.CODE_URBANISME,
}


# Mapping statut DILA → StatutVersion Beaume.
_STATUT_VERS_STATUT: dict[str, StatutVersion] = {
    "VIGUEUR": StatutVersion.EN_VIGUEUR,
    "VIGUEUR_DIFF": StatutVersion.EN_VIGUEUR,
    "MODIFIE": StatutVersion.MODIFIE,
    "MODIFIE_MORT_NE": StatutVersion.MODIFIE,
    "ABROGE": StatutVersion.ABROGE,
    "ABROGE_DIFF": StatutVersion.INCONNU,
    "PERIME": StatutVersion.ABROGE,
    "TRANSFERE": StatutVersion.ABROGE,
    "ANNULE": StatutVersion.ABROGE,
    "DISJOINT": StatutVersion.ABROGE,
    "DEPLACE": StatutVersion.ABROGE,
    "": StatutVersion.INCONNU,
    "MANQUANT": StatutVersion.INCONNU,
}


_SENTINELLES_DATE = ("2999-01-01", "2222-02-22")


def _map_statut(statut_dila: str, date_debut: date) -> StatutVersion:
    if statut_dila == "VIGUEUR_DIFF":
        if date_debut > date.today():
            return StatutVersion.FUTUR
        return StatutVersion.EN_VIGUEUR
    return _STATUT_VERS_STATUT.get(statut_dila, StatutVersion.INCONNU)


def _parse_date_debut(valeur: str | None) -> date | None:
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except (TypeError, ValueError):
        return None


def _parse_date_fin(valeur: str | None) -> date | None:
    if not valeur:
        return None
    if valeur in _SENTINELLES_DATE:
        return None
    try:
        return date.fromisoformat(valeur)
    except (TypeError, ValueError):
        return None


def _score_version(row: sqlite3.Row) -> tuple[int, int, str]:
    """Score de préférence pour départager deux versions à date_debut égale.

    Priorité :
    1. date_fin renseignée (plus d'information sur la période)
    2. texte non vide (version documentée)
    3. LEGIARTI le plus grand (version la plus récente)
    """
    a_date_fin = 1 if row["date_fin"] else 0
    a_texte = 1 if (row["texte"] or "").strip() else 0
    return (a_date_fin, a_texte, row["article_id"] or "")


class SourceDila:
    """Lecture du corpus DILA LEGI v2."""

    def __init__(self, chemin_db: Path, *, filtrer_conflits: bool = True) -> None:
        self.chemin_db = Path(chemin_db)
        if not self.chemin_db.is_file():
            raise FileNotFoundError(self.chemin_db)
        self.filtrer_conflits = filtrer_conflits
        self._conn: sqlite3.Connection | None = None
        self.versions_dedupliquees = 0

    def _connexion(self) -> sqlite3.Connection:
        if self._conn is None:
            uri = f"{self.chemin_db.resolve().as_uri()}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def fermer(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SourceDila":
        return self

    def __exit__(self, *args: object) -> None:
        self.fermer()

    def _vue(self) -> str:
        return (
            "versions_articles_sans_conflit_source"
            if self.filtrer_conflits
            else "versions_articles"
        )

    def compter(self, codes: tuple[str, ...] | None = None) -> int:
        conn = self._connexion()
        vue = self._vue()
        if codes:
            placeholders = ",".join("?" for _ in codes)
            requete = f"SELECT COUNT(*) FROM {vue} WHERE code IN ({placeholders})"
            (n,) = conn.execute(requete, codes).fetchone()
        else:
            (n,) = conn.execute(f"SELECT COUNT(*) FROM {vue}").fetchone()
        return int(n)

    def trouver_par_numero(self, numero: str, code_dila: str) -> Article | None:
        conn = self._connexion()
        vue = self._vue()
        requete = (
            f"SELECT article_id, code, numero, date_debut, date_fin, statut, "
            f"texte, article_famille_id FROM {vue} "
            f"WHERE numero = ? AND code = ? ORDER BY date_debut"
        )
        rows = conn.execute(requete, (numero, code_dila)).fetchall()
        if not rows:
            return None
        return self._construire_article(list(rows))

    def iter_articles(
        self,
        codes: tuple[str, ...] | None = None,
        limite: int | None = None,
    ) -> Iterator[Article]:
        conn = self._connexion()
        vue = self._vue()

        conditions = ["code IS NOT NULL"]
        params: list[str] = []
        if codes:
            placeholders = ",".join("?" for _ in codes)
            conditions.append(f"code IN ({placeholders})")
            params.extend(codes)

        clause_where = " AND ".join(conditions)
        requete = (
            f"SELECT article_id, code, numero, date_debut, date_fin, statut, "
            f"texte, article_famille_id FROM {vue} WHERE {clause_where}"
        )
        if limite is not None:
            requete += f" LIMIT {limite * 5}"

        groupes: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in conn.execute(requete, params):
            cle = row["article_famille_id"] or row["article_id"]
            groupes[cle].append(row)

        n_articles = 0
        for rows in groupes.values():
            rows.sort(key=lambda r: r["date_debut"] or "")
            article = self._construire_article(rows)
            if article is not None:
                yield article
                n_articles += 1
                if limite is not None and n_articles >= limite:
                    return

    def _construire_article(self, rows: list[sqlite3.Row]) -> Article | None:
        premiere = rows[0]
        code_dila = premiere["code"]
        code_beaume = _LEGITEXT_VERS_CODE.get(code_dila, CodeJuridique.CODE_AUTRE)

        # Toutes les versions d'un même article partagent le même
        # article_id (famille_id). Le LEGIARTI propre à chaque version
        # va dans `source`, pour la traçabilité DILA.
        article_id_famille = premiere["article_famille_id"] or premiere["article_id"]

        # Dédoublonner par date_debut : PRIMARY KEY de `versions` est
        # (article_id, date_debut). Deux LEGIARTI de la même famille
        # peuvent partager une date_debut.
        par_date: dict[str, sqlite3.Row] = {}
        for row in rows:
            date = row["date_debut"] or ""
            existant = par_date.get(date)
            if existant is None:
                par_date[date] = row
                continue
            if _score_version(row) > _score_version(existant):
                log.warning(
                    "Article %s : collision date_debut=%s, LEGIARTI %s "
                    "remplace %s",
                    article_id_famille, date,
                    row["article_id"], existant["article_id"],
                )
                par_date[date] = row
            else:
                log.warning(
                    "Article %s : collision date_debut=%s, LEGIARTI %s "
                    "ignoré (garde %s)",
                    article_id_famille, date,
                    row["article_id"], existant["article_id"],
                )
            self.versions_dedupliquees += 1

        versions: list[VersionArticle] = []
        versions_ignorees = 0
        for row in par_date.values():
            date_debut = _parse_date_debut(row["date_debut"])
            if date_debut is None:
                versions_ignorees += 1
                log.warning(
                    "Version %s ignorée : date_debut invalide (valeur=%r)",
                    row["article_id"], row["date_debut"],
                )
                continue
            date_fin = _parse_date_fin(row["date_fin"])
            statut = _map_statut(row["statut"] or "", date_debut)
            versions.append(
                VersionArticle(
                    article_id=IdentifiantLegifrance(valeur=article_id_famille),
                    numero=row["numero"] or "",
                    date_debut=date_debut,
                    date_fin=date_fin,
                    texte=row["texte"] or "",
                    statut=statut,
                    source=f"DILA-LEGI:{row['article_id']}",
                )
            )

        if not versions:
            return None

        return Article(
            id=IdentifiantLegifrance(valeur=article_id_famille),
            code=code_beaume,
            numero=premiere["numero"] or "",
            versions=versions,
        )