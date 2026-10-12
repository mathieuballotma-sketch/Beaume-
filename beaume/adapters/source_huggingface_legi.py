"""Adaptateur : charge les articles depuis le dataset LEGI Hugging Face.

Source : VinceGx33/legi-french-law-2025
Format : Parquet, 367 075 articles en vigueur (donnees DILA 2025).

Respecte le contrat SourceLegale. Aucune connexion reseau a l'execution
(le dataset est sauvegarde en local au prealable).
"""
from datetime import date
from pathlib import Path

from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.mapping_codes import code_depuis_titre
from beaume.legal.model import (
    Article,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)
from beaume.utils.logging import get_logger

log = get_logger("source_huggingface")

_DATE_FIN_SENTINELLE = date(2999, 1, 1)


class SourceHuggingFaceLegi:
    """Charge les articles LEGI depuis un dataset Hugging Face local."""

    def __init__(
        self,
        chemin_dataset: Path,
        codes_inclus: set[CodeJuridique] | None = None,
        limite: int | None = None,
    ) -> None:
        self.chemin_dataset = Path(chemin_dataset)
        self.codes_inclus = codes_inclus
        self.limite = limite

    def description(self) -> str:
        filtres = []
        if self.codes_inclus:
            filtres.append(f"{len(self.codes_inclus)} codes")
        if self.limite:
            filtres.append(f"limite {self.limite}")
        suffixe = f" ({', '.join(filtres)})" if filtres else ""
        return f"Dataset Hugging Face LEGI : {self.chemin_dataset}{suffixe}"

    def charger(self) -> list[Article]:
        if not self.chemin_dataset.exists():
            raise FileNotFoundError(
                f"Dataset introuvable : {self.chemin_dataset}"
            )

        try:
            from datasets import load_from_disk
        except ImportError as e:
            raise RuntimeError(
                "La lib 'datasets' est requise. "
                "Installe-la avec : pip install datasets"
            ) from e

        ds = load_from_disk(str(self.chemin_dataset))
        train = ds["train"]

        articles: list[Article] = []
        compteur = 0

        for row in train:
            if row.get("article_etat") != "VIGUEUR":
                continue

            code = code_depuis_titre(row.get("texte_titre"))
            if self.codes_inclus and code not in self.codes_inclus:
                continue

            article = self._construire_article(row, code)
            if article is None:
                continue

            articles.append(article)
            compteur += 1
            if self.limite and compteur >= self.limite:
                break

        log.info(
            "Charge %d articles depuis %s", len(articles), self.chemin_dataset,
        )
        return articles

    def _construire_article(
        self, row: dict, code: CodeJuridique
    ) -> Article | None:
        try:
            identifiant = IdentifiantLegifrance(valeur=row["article_id"])
        except Exception:
            return None

        texte = row.get("article_contenu_text") or ""
        if not texte.strip():
            return None

        date_debut = self._parser_date(row.get("date_debut"))
        if date_debut is None:
            return None

        date_fin = self._parser_date(row.get("date_fin"))
        if date_fin == _DATE_FIN_SENTINELLE:
            date_fin = None

        numero = str(row.get("article_num") or "").strip()
        if not numero:
            return None

        version = VersionArticle(
            article_id=identifiant,
            numero=numero,
            date_debut=date_debut,
            date_fin=date_fin,
            texte=texte,
            statut=StatutVersion.EN_VIGUEUR,
            source="dila",
        )

        return Article(
            id=identifiant,
            code=code,
            numero=numero,
            versions=[version],
        )

    def _parser_date(self, valeur) -> date | None:
        if valeur is None:
            return None
        if isinstance(valeur, date):
            return valeur
        s = str(valeur).strip()
        if not s:
            return None
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None
