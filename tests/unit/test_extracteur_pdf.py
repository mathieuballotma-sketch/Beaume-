"""Tests de l'adaptateur ExtracteurPDF branche sur le port Extracteur."""
from pathlib import Path
import pytest
import pymupdf

from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.ports.extracteur import Extracteur
from beaume.ports.registre import RegistreExtracteurs


def _make_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def test_adaptateur_respecte_contrat():
    """Le contrat est la loi : l'adaptateur DOIT le respecter."""
    assert isinstance(ExtracteurPDF(), Extracteur)


def test_supporte_pdf():
    e = ExtracteurPDF()
    assert e.supporte(Path("contrat.pdf"))
    assert e.supporte(Path("contrat.PDF"))
    assert not e.supporte(Path("contrat.docx"))
    assert not e.supporte(Path("contrat.txt"))


def test_extrait_texte_simple(tmp_path):
    pdf = tmp_path / "simple.pdf"
    _make_pdf(pdf, "Le present contrat prend effet le 1er janvier.")
    texte = ExtracteurPDF().extraire(pdf)
    assert "contrat" in texte
    assert "1er janvier" in texte


def test_fichier_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        ExtracteurPDF().extraire(tmp_path / "absent.pdf")


def test_integration_registre_choisit_pdf():
    """Loi d'inversion des dependances : le registre fait le choix."""
    r = RegistreExtracteurs()
    r.enregistrer(ExtracteurPDF())
    assert isinstance(r.pour(Path("a.pdf")), ExtracteurPDF)
    assert r.pour(Path("a.txt")) is None
