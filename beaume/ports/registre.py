"""Registre generique : permet d'ajouter des implementations sans
modifier le code appelant.
"""
from pathlib import Path

from beaume.ports.extracteur import Extracteur


class RegistreExtracteurs:
    def __init__(self) -> None:
        self._extracteurs: list[Extracteur] = []

    def enregistrer(self, e: Extracteur) -> None:
        if not isinstance(e, Extracteur):
            raise TypeError(
                f"{type(e).__name__} ne respecte pas le contrat Extracteur"
            )
        self._extracteurs.append(e)

    def pour(self, path: Path) -> Extracteur | None:
        for e in self._extracteurs:
            if e.supporte(path):
                return e
        return None

    def formats_supportes(self) -> list[str]:
        return [type(e).__name__ for e in self._extracteurs]
