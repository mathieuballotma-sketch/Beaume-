"""Port : contrat d'un index vectoriel.

Un index stocke des elements (id, vecteur, metadonnees) et permet
de retrouver les k plus proches d'un vecteur requete.
Le port ne connait AUCUNE technologie de stockage.
"""
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ElementIndexe:
    id: str
    vecteur: tuple[float, ...]
    metadonnees: dict[str, Any]


@dataclass(frozen=True)
class ResultatRecherche:
    id: str
    score: float            # 0 = identique, 1 = orthogonal, 2 = oppose
    metadonnees: dict[str, Any]


@runtime_checkable
class IndexVectoriel(Protocol):
    def ajouter(self, elements: list[ElementIndexe]) -> None: ...
    def rechercher(
        self, vecteur: list[float], k: int = 5
    ) -> list[ResultatRecherche]: ...
    def taille(self) -> int: ...
    def vider(self) -> None: ...
