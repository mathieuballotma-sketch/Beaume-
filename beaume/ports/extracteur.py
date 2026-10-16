"""Port : contrat d'extraction de texte depuis un fichier.

Ce fichier ne connait AUCUN format concret. C'est volontaire.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PageExtraite:
    """Une page avec sa position dans le texte concatene du document.

    Sert a tracer l'origine d'un fait : quel fichier, quelle page.
    """
    numero: int          # 1, 2, 3...
    texte: str
    debut_car: int       # offset du debut dans le texte concatene
    fin_car: int         # offset de la fin


@runtime_checkable
class Extracteur(Protocol):
    def supporte(self, path: Path) -> bool: ...
    def extraire(self, path: Path) -> str: ...
    def extraire_avec_pages(self, path: Path) -> list[PageExtraite]: ...