"""Adaptateur de lecture du corpus DILA LEGI v2.

Lit la base SQLite produite par `scripts/preparer_legi_dila.py` (Codex)
et expose les articles avec toutes leurs versions, au format attendu
par `DepotSQLite.enregistrer()`.

Source : vue `versions_articles_sans_conflit_source`, qui exclut les
identifiants aux copies divergentes. Les textes non codifiés (code NULL)
sont ignorés : ils ne correspondent à aucun `CodeJuridique` de Beaume.

Correctifs du 2026-10-20 (audit d'équipe) :

1. `_score_version` préfère la version OUVERTE (date_fin=None ou
   sentinelle 2999) en cas de collision date_debut. Avant, la version
   avec date_fin gagnait, ce qui pouvait écarter une version toujours
   applicable au profit d'une version fermée.

2. `_parse_date_fin` retourne (date, valide). Une date de fin invalide
   (ex: "inconnue") force le statut INCONNU au lieu de le laisser
   passer en EN_VIGUEUR éternel.

3. `trouver_par_numero` groupe par article_famille_id. Si plusieurs
   familles partagent le même numéro, retourne None avec warning
   (ne pas deviner). Un paramètre `article_famille_id` permet de
   cibler une famille précise.

4. `iter_articles` ne met plus de LIMIT SQL (qui coupait au milieu
   d'un article). On charge tout, groupe en Python, puis coupe à
   `limite` articles complets.

Le LEGIARTI propre à chaque version est conservé dans `source`, pour
permettre de remonter au XML DILA original. Le rendu doit utiliser
`source` (et non `article_id`) pour construire les liens Légifrance.

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
    """Parse une date de début DILA.

    Les sentinelles 2999-01-01 et 2222-02-22 sont conservées comme dates
    réelles, pour que est_en_vigueur_a() retourne False aux dates usuelles.
    """
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except (TypeError, ValueError):
        return None


def _parse_date_fin(valeur: str | None) -> tuple[date | None, bool]:
    """Parse une date de fin DILA.

    Retourne (date_fin, valide) :
    - (None, True)  si pas de date (version ouverte)
    - (date, True)  si date valide
    - (None, False) si date invalide (à traiter comme INCONNU, pas EN_VIGUEUR)

    Une date invalide ne prouve pas que la version est ouverte.
    """
    if not valeur:
        return None, True
    if valeur in _SENTINELLES_DATE:
        return None, True
    try:
        return date.fromisoformat(valeur), True
    except (TypeError, ValueError):
        return None, False


def _score_version(row: sqlite3.Row) -> tuple[int, int, str]:
    """Score de préférence pour départager deux versions à date_debut égale.

    Priorité (du plus important au moins important) :
    1. version OUVERTE (pas de date_fin, ou sentinelle 2999) : une version
       qui continue est plus informative qu'une version qui s'arrête
    2. texte non vide (version documentée)
    3. LEGIARTI le plus récent
    """
    date_fin = row["date_fin"]
    est_ouverte = 1 if (not date_fin or date_fin in _SENTINELLES_DATE) else 0
    a_texte = 1 if (row["texte"] or "").strip() else 0
    return (est_ouverte, a_texte, row["article_id"] or "")


class SourceDila:
    """Lecture du corpus DILA LEGI v2."""

    def __init__(self, chemin_db: Path, *, filtrer_conflits: bool = True) -> None:
        self.chemin_db = Path(chemin_db)
        if not self.chemin_db.is_file():
            raise FileNotFoundError(self.chemin_db)
        self.filtrer_conflits = filtrer_conflits
        self._conn: sqlite3.Connection | None = None
        self.versions_dedupliquees = 0
        self.versions_date_fin_invalide = 0

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
        """Compte les versions (filtrées par code DILA si fourni)."""
        conn = self._connexion()
        vue = self._vue()
        if codes:
            placeholders = ",".join("?" for _ in codes)
            requete = f"SELECT COUNT(*) FROM {vue} WHERE code IN ({placeholders})"
            (n,) = conn.execute(requete, codes).fetchone()
        else:
            (n,) = conn.execute(f"SELECT COUNT(*) FROM {vue}").fetchone()
        return int(n)

    def trouver_par_numero(
        self,
        numero: str,
        code_dila: str,
        article_famille_id: str | None = None,
    ) -> Article | None:
        """Retourne un Article par numéro + code DILA, ou None.

        Si `article_famille_id` est fourni, cible cette famille précise.
        Sinon :
        - 0 famille trouvée : retourne None
        - 1 famille : retourne l'article
        - >1 familles : retourne None avec warning (ne pas deviner)

        Pour lever l'ambiguïté sur un numéro réutilisé (renumérotation,
        republication), passer `article_famille_id` explicitement.
        """
        conn = self._connexion()
        vue = self._vue()

        conditions = ["numero = ?", "code = ?"]
        params: list[str] = [numero, code_dila]
        if article_famille_id:
            conditions.append("COALESCE(article_famille_id, article_id) = ?")
            params.append(article_famille_id)

        clause_where = " AND ".join(conditions)
        requete = (
            f"SELECT article_id, code, numero, date_debut, date_fin, statut, "
            f"texte, article_famille_id FROM {vue} "
            f"WHERE {clause_where} ORDER BY date_debut"
        )
        rows = conn.execute(requete, params).fetchall()
        if not rows:
            return None

        familles: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            cle = row["article_famille_id"] or row["article_id"]
            familles[cle].append(row)

        if article_famille_id:
            if article_famille_id not in familles:
                return None
            return self._construire_article(familles[article_famille_id])

        if len(familles) > 1:
            log.warning(
                "trouver_par_numero(%r, %r) : %d familles distinctes (%s). "
                "Ambigu, retourne None. Utiliser article_famille_id.",
                numero, code_dila, len(familles), list(familles.keys()),
            )
            return None

        return self._construire_article(list(familles.values())[0])

    def iter_articles(
        self,
        codes: tuple[str, ...] | None = None,
        limite: int | None = None,
    ) -> Iterator[Article]:
        """Itère les `Article` complets, avec toutes leurs versions.

        Pas de LIMIT SQL : on charge tout, on groupe en Python, puis on
        coupe à `limite` articles complets. Un LIMIT SQL couperait au
        milieu d'un article multi-version et perdrait des versions.
        """
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
            date_str = row["date_debut"] or ""
            existant = par_date.get(date_str)
            if existant is None:
                par_date[date_str] = row
                continue
            if _score_version(row) > _score_version(existant):
                log.warning(
                    "Article %s : collision date_debut=%s, LEGIARTI %s "
                    "remplace %s",
                    article_id_famille, date_str,
                    row["article_id"], existant["article_id"],
                )
                par_date[date_str] = row
            else:
                log.warning(
                    "Article %s : collision date_debut=%s, LEGIARTI %s "
                    "ignoré (garde %s)",
                    article_id_famille, date_str,
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

            date_fin, date_fin_valide = _parse_date_fin(row["date_fin"])

            if not date_fin_valide:
                # Date de fin invalide : ne pas laisser passer en EN_VIGUEUR.
                # Marquer INCONNU pour que le vérificateur rejette.
                self.versions_date_fin_invalide += 1
                log.warning(
                    "Version %s : date_fin invalide (%r), statut forcé INCONNU",
                    row["article_id"], row["date_fin"],
                )
                statut = StatutVersion.INCONNU
            else:
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