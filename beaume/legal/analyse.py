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

    # Nouveaux champs de tracabilite (2026-10-16).
    erreur: str | None = None
    fichiers_ignores: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def nb_citations(self) -> int:
        return len(self.citations)

    @property
    def etat(self) -> str:
        """Etat du rapport : COMPLET, PARTIEL ou ECHEC."""
        if self.erreur:
            return "ECHEC"
        if self.fichiers_ignores:
            return "PARTIEL"
        if self.est_vide():
            return "ECHEC"
        return "COMPLET"

    def est_vide(self) -> bool:
        return (
            not self.contexte.strip()
            and not self.citations
            and not self.problemes_juridiques
        )