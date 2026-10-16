"""Verifie que le lecteur propage les pages dans FichierExtrait."""
from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.application.lecteur_dossier import LecteurDossier
from beaume.ports.registre import RegistreExtracteurs


@pytest.fixture
def dossier_avec_pdf(tmp_path: Path) -> Path:
    """Un dossier avec un PDF de 3 pages."""
    dossier = tmp_path / "dossier"
    dossier.mkdir()
    chemin = dossier / "test.pdf"
    doc = pymupdf.open()
    for texte in ["Page 1 contenu long", "Page 2 contenu long", "Page 3 contenu long"]:
        page = doc.new_page()
        page.insert_text((50, 50), texte)
    doc.save(str(chemin))
    doc.close()
    return dossier


def test_pages_sont_propagees(dossier_avec_pdf: Path):
    registre = RegistreExtracteurs()
    registre.enregistrer(ExtracteurPDF())
    lecteur = LecteurDossier(registre)
    resultat = lecteur.lire(dossier_avec_pdf)
    assert len(resultat.fichiers) == 1
    fichier = resultat.fichiers[0]
    assert fichier.ok
    assert len(fichier.pages) == 3
    assert [p.numero for p in fichier.pages] == [1, 2, 3]


def test_texte_reconstruit_depuis_pages(dossier_avec_pdf: Path):
    registre = RegistreExtracteurs()
    registre.enregistrer(ExtracteurPDF())
    lecteur = LecteurDossier(registre)
    resultat = lecteur.lire(dossier_avec_pdf)
    fichier = resultat.fichiers[0]
    assert "Page 1" in fichier.texte
    assert "Page 2" in fichier.texte
    assert "Page 3" in fichier.texte


def test_offsets_pages_sont_dans_texte(dossier_avec_pdf: Path):
    registre = RegistreExtracteurs()
    registre.enregistrer(ExtracteurPDF())
    lecteur = LecteurDossier(registre)
    resultat = lecteur.lire(dossier_avec_pdf)
    fichier = resultat.fichiers[0]
    for page in fichier.pages:
        extrait = fichier.texte[page.debut_car:page.fin_car]
        assert extrait == page.texte