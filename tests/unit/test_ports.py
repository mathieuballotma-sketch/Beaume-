"""Tests du contrat Extracteur et du registre."""
from pathlib import Path
import pytest

from beaume.ports.extracteur import Extracteur
from beaume.ports.registre import RegistreExtracteurs


class FauxExtracteurPDF:
    def supporte(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"
    def extraire(self, path: Path) -> str:
        return f"contenu de {path.name}"


class FauxExtracteurTXT:
    def supporte(self, path: Path) -> bool:
        return path.suffix.lower() == ".txt"
    def extraire(self, path: Path) -> str:
        return f"contenu de {path.name}"


def test_extracteur_conforme():
    assert isinstance(FauxExtracteurPDF(), Extracteur)


def test_extracteur_non_conforme():
    class Mauvais:
        pass
    assert not isinstance(Mauvais(), Extracteur)


def test_registre_choisit_bon_extracteur():
    r = RegistreExtracteurs()
    r.enregistrer(FauxExtracteurPDF())
    r.enregistrer(FauxExtracteurTXT())
    pdf = r.pour(Path("a.pdf"))
    txt = r.pour(Path("a.txt"))
    assert isinstance(pdf, FauxExtracteurPDF)
    assert isinstance(txt, FauxExtracteurTXT)
    assert r.pour(Path("a.docx")) is None


def test_registre_rejette_non_conforme():
    r = RegistreExtracteurs()
    with pytest.raises(TypeError):
        r.enregistrer(object())  # type: ignore


def test_ajout_extracteur_sans_modifier_registre():
    class FauxDOCX:
        def supporte(self, path: Path) -> bool:
            return path.suffix.lower() == ".docx"
        def extraire(self, path: Path) -> str:
            return "docx"

    r = RegistreExtracteurs()
    r.enregistrer(FauxExtracteurPDF())
    r.enregistrer(FauxDOCX())
    assert r.pour(Path("x.docx")) is not None
