"""Tests de la machine a etats."""
from pathlib import Path
import pytest

from beaume.application.etats import EtatDocument
from beaume.application.machine import Document, TransitionIllegale


def test_parcours_nominal():
    d = Document(chemin=Path("x.pdf"))
    assert d.etat == EtatDocument.DEPOSE
    d.transition(EtatDocument.EXTRAIT, "ok")
    d.transition(EtatDocument.DECOUPE, "ok")
    d.transition(EtatDocument.INDEXE, "ok")
    d.transition(EtatDocument.ANALYSE, "ok")
    d.transition(EtatDocument.VERIFIE, "ok")
    d.transition(EtatDocument.PUBLIE, "ok")
    assert d.etat == EtatDocument.PUBLIE


def test_transition_illegale():
    d = Document(chemin=Path("x.pdf"))
    with pytest.raises(TransitionIllegale):
        d.transition(EtatDocument.ANALYSE)


def test_etat_terminal_ne_bouge_plus():
    d = Document(chemin=Path("x.pdf"))
    d.transition(EtatDocument.EXTRAIT)
    d.transition(EtatDocument.ECHEC, "erreur")
    with pytest.raises(TransitionIllegale):
        d.transition(EtatDocument.DECOUPE)


def test_echec_depuis_nimporte_ou():
    d = Document(chemin=Path("x.pdf"))
    d.transition(EtatDocument.EXTRAIT)
    d.transition(EtatDocument.DECOUPE)
    d.echouer("plus de RAM")
    assert d.etat == EtatDocument.ECHEC


def test_historique_conserve():
    d = Document(chemin=Path("x.pdf"))
    d.transition(EtatDocument.EXTRAIT, "extraction reussie")
    assert len(d.historique) == 2
    assert d.historique[0][1] == EtatDocument.DEPOSE
    assert d.historique[1][1] == EtatDocument.EXTRAIT
