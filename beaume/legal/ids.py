"""Identifiants Legifrance. Format strict, valide une fois pour toutes."""
import re
from enum import Enum
from pydantic import BaseModel, field_validator

_PATTERN = re.compile(r"^(LEGITEXT|LEGIARTI|JURITEXT)\d{12}$")


class TypeIdentifiant(str, Enum):
    TEXTE = "LEGITEXT"
    ARTICLE = "LEGIARTI"
    JURISPRUDENCE = "JURITEXT"


class IdentifiantLegifrance(BaseModel, frozen=True):
    """Identifiant canonique d'un objet juridique.

    Exemple : LEGIARTI000006900898 (article L. 1234-1 du Code du travail).
    """
    valeur: str

    @field_validator("valeur")
    @classmethod
    def _check_format(cls, v: str) -> str:
        if not _PATTERN.match(v):
            raise ValueError(
                f"Identifiant Legifrance invalide : {v!r}. "
                "Format attendu : LEGITEXT/LEGIARTI/JURITEXT + 12 chiffres."
            )
        return v

    @property
    def type(self) -> TypeIdentifiant:
        return TypeIdentifiant(self.valeur[:8])
