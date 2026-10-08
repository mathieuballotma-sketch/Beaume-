"""Etats d'un document client dans le pipeline Beaume."""
from enum import Enum


class EtatDocument(str, Enum):
    DEPOSE = "depose"
    EXTRAIT = "extrait"
    DECOUPE = "decoupe"
    INDEXE = "indexe"
    ANALYSE = "analyse"
    VERIFIE = "verifie"
    PUBLIE = "publie"
    ECHEC = "echec"


TRANSITIONS: dict[EtatDocument, set[EtatDocument]] = {
    EtatDocument.DEPOSE:   {EtatDocument.EXTRAIT, EtatDocument.ECHEC},
    EtatDocument.EXTRAIT:  {EtatDocument.DECOUPE, EtatDocument.ECHEC},
    EtatDocument.DECOUPE:  {EtatDocument.INDEXE, EtatDocument.ECHEC},
    EtatDocument.INDEXE:   {EtatDocument.ANALYSE, EtatDocument.ECHEC},
    EtatDocument.ANALYSE:  {EtatDocument.VERIFIE, EtatDocument.ECHEC},
    EtatDocument.VERIFIE:  {EtatDocument.PUBLIE, EtatDocument.ECHEC},
    EtatDocument.PUBLIE:   set(),
    EtatDocument.ECHEC:    set(),
}
