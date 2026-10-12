"""Port : contrat d'une source d'articles de loi.

Une source sait charger une liste d'articles depuis quelque part :
un fichier local, un dump DILA, une API Legifrance, etc.
Le port ne connait AUCUN emplacement concret.
"""
from typing import Protocol, runtime_checkable

from beaume.legal.model import Article


@runtime_checkable
class SourceLegale(Protocol):
    def charger(self) -> list[Article]: ...
    def description(self) -> str: ...