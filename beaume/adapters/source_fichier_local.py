"""Adaptateur : lit des articles de loi depuis un fichier JSON local.

Respecte le contrat SourceLegale. Aucune connexion reseau.
Le format JSON est volontairement simple et lisible :
un objet racine {"articles": [...]}.
"""
import json
from pathlib import Path

from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)


class SourceFichierLocal:
    """Charge une liste d'articles depuis un fichier JSON."""

    def __init__(self, chemin: Path) -> None:
        self.chemin = Path(chemin)

    def description(self) -> str:
        return f"Fichier local : {self.chemin}"

    def charger(self) -> list[Article]:
        if not self.chemin.exists():
            raise FileNotFoundError(
                f"Fichier d'articles introuvable : {self.chemin}"
            )

        with open(self.chemin, encoding="utf-8") as f:
            donnees = json.load(f)

        articles_bruts = donnees.get("articles", [])
        if not isinstance(articles_bruts, list):
            raise ValueError(
                "Le fichier doit contenir une liste 'articles'."
            )

        return [self._construire_article(a) for a in articles_bruts]

    def _construire_article(self, brut: dict) -> Article:
        identifiant = IdentifiantLegifrance(valeur=brut["id"])
        code = CodeJuridique(brut["code"])
        numero = brut["numero"]

        versions: list[VersionArticle] = []
        for v in brut.get("versions", []):
            versions.append(
                VersionArticle(
                    article_id=IdentifiantLegifrance(valeur=v["article_id"]),
                    numero=v["numero"],
                    date_debut=v["date_debut"],
                    date_fin=v.get("date_fin"),
                    texte=v["texte"],
                    statut=StatutVersion(v["statut"]),
                    source=v["source"],
                )
            )

        return Article(
            id=identifiant,
            code=code,
            numero=numero,
            versions=versions,
        )