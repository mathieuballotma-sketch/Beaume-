"""Port : contrat d'un resolveur d'article strict.

Un resolveur repond a la question : pour un triplet
(code, numero, date_reference), quelle version unique de l'article
est applicable a cette date ?

Il ne devine JAMAIS. Il retourne un statut typé qui distingue une
resolution unique et traceable, une reference absente du corpus,
l'absence de version a la date, l'ambiguite entre familles ou entre
versions d'une meme famille, une provenance insuffisante, des
donnees invalides, ou une erreur technique.

Le parametre `strict` NE CHANGE PAS le statut retourne. Il controle
uniquement la richesse du diagnostic :
- strict=True  : `candidats` reste vide, message court ;
- strict=False : `candidats` renseigne, message plus detaille.

Aucun mode permissif n'existe : une resolution non unique n'est
jamais retournee comme si elle l'etait. C'est ce qui distingue ce
port du DepotArticles.trouver() historique, dont le LIMIT 1 ne
prouve pas l'unicite.

Invariants attendus de toute implementation :
1. normaliser le numero via normaliser_numero() ;
2. chercher dans versions.numero (numero historique), pas
   articles.numero ;
3. examiner TOUS les candidats applicables avant de declarer
   l'unicite ;
4. traiter 2999-01-01 et 2222-02-22 comme date_fin infinie ;
5. borner les dates de facon inclusive (debut <= D <= fin) ;
6. ne jamais laisser fuir une exception SQLite : toute erreur
   technique devient ERREUR_TECHNIQUE avec message ;
7. ne pas modifier trouver() ni Article.version_a() : la voie
   stricte est additive.

Note : runtime_checkable verifie la PRESENCE des methodes, pas leur
signature. Un faux depot qui declare resoudre_article avec une
signature differente passerait isinstance() ; les tests doivent
couvrir le comportement, pas seulement le type.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Protocol, runtime_checkable

from beaume.legal.model import CodeJuridique


class StatutResolution(str, Enum):
    """Resultat d'une tentative de resolution stricte."""

    UNIQUE = "unique"
    REFERENCE_ABSENTE = "reference_absente"
    AUCUNE_VERSION_A_LA_DATE = "aucune_version_a_la_date"
    AMBIGUITE_FAMILLES = "ambiguite_familles"
    AMBIGUITE_VERSIONS = "ambiguite_versions"
    PROVENANCE_INSUFFISANTE = "provenance_insuffisante"
    DONNEES_INCOHERENTES = "donnees_incoherentes"
    ERREUR_TECHNIQUE = "erreur_technique"


@dataclass(frozen=True)
class ResolutionArticle:
    """Resultat detaille d'une resolution stricte.

    Champs obligatoires selon le statut :
    - UNIQUE                    : article_id_famille, version_date_debut,
                                  version_legiarti, code, numero_normalise.
    - PROVENANCE_INSUFFISANTE   : article_id_famille, version_date_debut,
                                  code, numero_normalise ;
                                  version_legiarti reste None.
    - AMBIGUITE_FAMILLES        : candidats (identifiants de famille).
    - AMBIGUITE_VERSIONS        : article_id_famille, candidats
                                  ("YYYY-MM-DD/LEGIARTI").
    - REFERENCE_ABSENTE         : aucun champ obligatoire.
    - AUCUNE_VERSION_A_LA_DATE  : aucun champ obligatoire.
    - DONNEES_INCOHERENTES      : message.
    - ERREUR_TECHNIQUE          : message.

    `candidats` n'est renseigne que lorsque la resolution n'est pas
    unique. Il sert au diagnostic, jamais a choisir a la place de
    l'appelant.
    """

    statut: StatutResolution
    article_id_famille: str | None = None
    version_date_debut: date | None = None
    version_legiarti: str | None = None
    code: CodeJuridique | None = None
    numero_normalise: str | None = None
    candidats: tuple[str, ...] = ()
    message: str = ""

    @property
    def est_unique(self) -> bool:
        return self.statut == StatutResolution.UNIQUE


@runtime_checkable
class ResolveurArticles(Protocol):
    """Contrat d'un depot capable de resoudre strictement une reference.

    Volontairement distinct de DepotArticles : tous les depots
    (memoire, index, etc.) n'ont pas besoin de porter un resolveur
    temporel strict. Elargir DepotArticles, qui est runtime_checkable,
    casserait silencieusement tout faux depot existant.
    """

    def resoudre_article(
        self,
        code: CodeJuridique,
        numero: str,
        date_reference: date,
        *,
        strict: bool = True,
    ) -> ResolutionArticle: ...
