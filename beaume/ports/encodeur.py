"""Port : contrat d'encodage de textes en vecteurs.

Le port est PUR : aucune dependance a Ollama, LanceDB, ou quoi que
ce soit. N'importe quelle implementation peut le satisfaire.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class Encodeur(Protocol):
    @property
    def dimension(self) -> int: ...
    def encoder(self, textes: list[str]) -> list[list[float]]: ...
