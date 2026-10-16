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
    """Codes juridiques francais."""
    CODE_CIVIL = "code_civil"
    CODE_PENAL = "code_penal"
    CODE_TRAVAIL = "code_travail"
    CODE_COMMERCE = "code_commerce"
    CODE_CONSOMMATION = "code_consommation"
    CODE_SECURITE_SOCIALE = "code_securite_sociale"
    CODE_PROCEDURE_CIVILE = "code_procedure_civile"
    CODE_PROCEDURE_PENALE = "code_procedure_penale"
    CODE_SANTE_PUBLIQUE = "code_sante_publique"
    CODE_RURAL = "code_rural"
    CODE_TRANSPORTS = "code_transports"
    CODE_ENVIRONNEMENT = "code_environnement"
    CODE_COLLECTIVITES_TERRITORIALES = "code_collectivites_territoriales"
    CODE_MONETAIRE_FINANCIER = "code_monetaire_financier"
    CODE_EDUCATION = "code_education"
    CODE_CONSTRUCTION_HABITATION = "code_construction_habitation"
    CODE_ACTION_SOCIALE_FAMILLES = "code_action_sociale_familles"
    CODE_DEFENSE = "code_defense"
    CODE_FONCTION_PUBLIQUE = "code_fonction_publique"
    CODE_ENERGIE = "code_energie"
    CODE_SECURITE_INTERIEURE = "code_securite_interieure"
    CODE_ETRANGERS = "code_etrangers"
    CODE_URBANISME = "code_urbanisme"
    CODE_AUTRE = "code_autre"


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
    # Nouveaux champs de tracabilite (2026-10-16).
    # - pages   : numeros de page du dossier ou le fait a ete trouve.
    # - fichier : nom du fichier source (ex: "conclusions.pdf").
    pages: tuple[int, ...] = ()
    fichier: str = ""


class StatutVerification(str, Enum):
    VALIDE = "valide"
    INTROUVABLE = "introuvable"
    VERSION_INCORRECTE = "version_incorrecte"
    ABROGE = "abroge"
    TEXTE_DIFFERENT = "texte_different"
    EXTRAIT_MANQUANT = "extrait_manquant"


class ResultatVerification(BaseModel, frozen=True):
    statut: StatutVerification
    citation: Citation
    version: VersionArticle | None = None
    message: str = ""

    @property
    def est_valide(self) -> bool:
        return self.statut == StatutVerification.VALIDE