"""Port : contrat d'un generateur de texte (LLM local).

Un generateur prend un prompt et retourne une reponse textuelle.
Le port ne connait AUCUN modele ni fournisseur concret.
"""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ReponseLLM:
    """Reponse d'un LLM, avec ses metadonnees."""
    texte: str
    modele: str
    duree_s: float
    tokens_prompt: int | None = None
    tokens_reponse: int | None = None


@runtime_checkable
class Generateur(Protocol):
    def generer(
        self,
        prompt: str,
        temperature: float = 0.2,
    ) -> ReponseLLM: ...
    def nom_modele(self) -> str: ...
