"""Faux index vectoriel en memoire : deterministe, sans dependance.

Sert aux tests unitaires. Ne PAS utiliser en production.
"""
import math

from beaume.ports.index_vectoriel import (
    ElementIndexe,
    ResultatRecherche,
)


def _distance_cosinus(a: list[float], b: list[float]) -> float:
    """Distance cosinus : 0 = identique, 2 = oppose. Calcul pur."""
    if len(a) != len(b):
        raise ValueError("Vecteurs de dimensions differentes")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


class IndexMemoire:
    def __init__(self) -> None:
        self._elements: list[ElementIndexe] = []

    def ajouter(self, elements: list[ElementIndexe]) -> None:
        for e in elements:
            if not isinstance(e.vecteur, tuple):
                raise TypeError("vecteur doit etre un tuple")
            self._elements.append(e)

    def rechercher(
        self, vecteur: list[float], k: int = 5
    ) -> list[ResultatRecherche]:
        if k <= 0:
            raise ValueError("k doit etre > 0")
        resultats = [
            ResultatRecherche(
                id=e.id,
                score=_distance_cosinus(vecteur, list(e.vecteur)),
                metadonnees=dict(e.metadonnees),
            )
            for e in self._elements
        ]
        resultats.sort(key=lambda r: r.score)
        return resultats[:k]

    def taille(self) -> int:
        return len(self._elements)

    def vider(self) -> None:
        self._elements.clear()
