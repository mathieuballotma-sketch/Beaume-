"""Tests du contrat Extracteur et du registre."""
from pathlib import Path

import pytest

from beaume.ports.extracteur import Extracteur, PageExtraite
from beaume.ports.registre import RegistreExtracteurs


def _page_unique(texte: str) -> list[PageExtraite]:
    return [PageExtraite(
        numero=1,
        texte=texte,
        debut_car=0,
        fin_car=len(texte),
    )]


class FauxExtracteurPDF:
    def supporte(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def extraire(self, path: Path) -> str:
        return f"contenu de {path.name}"

    def extraire_avec_pages(self, path: Path) -> list[PageExtraite]:
        return _page_unique(f"contenu de {path.name}")


class FauxExtracteurTXT:
    def supporte(self, path: Path) -> bool:
        return path.suffix.lower() == ".txt"

    def extraire(self, path: Path) -> str:
        return f"contenu de {path.name}"

    def extraire_avec_pages(self, path: Path) -> list[PageExtraite]:
        return _page_unique(f"contenu de {path.name}")


def test_extracteur_conforme():
    assert isinstance(FauxExtracteurPDF(), Extracteur)


def test_extracteur_non_conforme():
    class Mauvais:
        pass
    assert not isinstance(Mauvais(), Extracteur)


def test_extracteur_sans_pages_non_conforme():
    class SansPages:
        def supporte(self, path: Path) -> bool:
            return True
        def extraire(self, path: Path) -> str:
            return "x"
    assert not isinstance(SansPages(), Extracteur)


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
        def extraire_avec_pages(self, path: Path) -> list[PageExtraite]:
            return _page_unique("docx")

    r = RegistreExtracteurs()
    r.enregistrer(FauxExtracteurPDF())
    r.enregistrer(FauxDOCX())
    assert r.pour(Path("x.docx")) is not None