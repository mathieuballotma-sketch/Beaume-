"""Port : contrat d'extraction de texte depuis un fichier.

Ce fichier ne connait AUCUN format concret. C'est volontaire.
"""
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Extracteur(Protocol):
    def supporte(self, path: Path) -> bool: ...
    def extraire(self, path: Path) -> str: ...
