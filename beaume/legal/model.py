"""Ontologie juridique Beaume.

Regle d'or : un article n'existe qu'a une date. Toute citation doit
porter une date de reference. Le verificateur est la seule autorite
qui decide si une citation est valide.
"""
from datetime import date
from enum import Enum
from pydantic import BaseModel

from beaume.legal.ids import IdentifiantLegifrance


class CodeJuridique(str, Enum):
    CODE_CIVIL = "code_civil"
    CODE_TRAVAIL = "code_travail"
    CODE_PENAL = "code_penal"
    CODE_COMMERCE = "code_commerce"
    CODE_PROCEDURE_CIVILE = "code_procedure_civile"
    CODE_CONSOMMATION = "code_consommation"
    CODE_SECURITE_SOCIALE = "code_securite_sociale"


class StatutVersion(str, Enum):
    EN_VIGUEUR = "en_vigueur"
    ABROGE = "abroge"
    MODIFIE = "modifie"
    FUTUR = "futur"
    INCONNU = "inconnu"


class VersionArticle(BaseModel, frozen=True):
    article_id: IdentifiantLegifrance
    numero: str
    date_debut: date
    date_fin: date | None = None
    texte: str
    statut: StatutVersion
    source: str

    def est_en_vigueur_a(self, d: date) -> bool:
        if d < self.date_debut:
            return False
        if self.date_fin is None:
            return True
        return d <= self.date_fin


class Article(BaseModel):
    id: IdentifiantLegifrance
    code: CodeJuridique
    numero: str
    versions: list[VersionArticle]

    def version_a(self, d: date) -> VersionArticle | None:
        for v in self.versions:
            if v.est_en_vigueur_a(d):
                return v
        return None


class Citation(BaseModel):
    code: CodeJuridique
    numero: str
    date_reference: date
    extrait: str | None = None


class StatutVerification(str, Enum):
    VALIDE = "valide"
    INTROUVABLE = "introuvable"
    VERSION_INCORRECTE = "version_incorrecte"
    ABROGE = "abroge"
    TEXTE_DIFFERENT = "texte_different"


class ResultatVerification(BaseModel, frozen=True):
    statut: StatutVerification
    citation: Citation
    version: VersionArticle | None = None
    message: str = ""

    @property
    def est_valide(self) -> bool:
        return self.statut == StatutVerification.VALIDE
