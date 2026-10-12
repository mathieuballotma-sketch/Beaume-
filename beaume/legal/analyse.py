"""Modele du resultat d'une analyse de dossier."""
from datetime import date
from pydantic import BaseModel, Field

from beaume.legal.model import Citation


class Analyse(BaseModel):
    contexte: str = ""
    parties: list[str] = Field(default_factory=list)
    demandes: list[str] = Field(default_factory=list)
    problemes_juridiques: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    date_reference: date

    @property
    def nb_citations(self) -> int:
        return len(self.citations)

    def est_vide(self) -> bool:
        return (
            not self.contexte.strip()
            and not self.citations
            and not self.problemes_juridiques
        )
