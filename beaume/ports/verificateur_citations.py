"""Port : contrat d'un verificateur de citations.

Prend une Citation produite par le LLM et retourne un verdict :
l'article existe-t-il dans le corpus, a la bonne date, avec le bon texte ?

Le port ne connait AUCUNE source concrete (SQLite, API, fichier).
"""
from typing import Protocol, runtime_checkable

from beaume.legal.model import Citation, ResultatVerification


@runtime_checkable
class VerificateurCitations(Protocol):
    def verifier(self, citation: Citation) -> ResultatVerification: ...
    def verifier_toutes(
        self, citations: list[Citation]
    ) -> list[ResultatVerification]: ...
