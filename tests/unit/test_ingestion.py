"""Tests du pipeline d'ingestion complet."""
from pathlib import Path
import pymupdf
import pytest

from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.application.ingestion import IngestionDossier
from beaume.ports.registre import RegistreExtracteurs
from beaume.testing.index_memoire import IndexMemoire


class FauxEncodeur:
    def __init__(self, dimension: int = 8) -> None:
        self._dimension = dimension
        self.appels: list[list[str]] = []

    @property
    def dimension(self) -> int:
        return self._dimension

    def encoder(self, textes: list[str]) -> list[list[float]]:
        self.appels.append(list(textes))
        resultats = []
        for t in textes:
            h = hash(t) % 1000
            resultats.append(
                [float((h + i) % 100) for i in range(self._dimension)]
            )
        return resultats


def _make_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def _registre() -> RegistreExtracteurs:
    r = RegistreExtracteurs()
    r.enregistrer(ExtracteurPDF())
    return r


def test_ingestion_dossier_vide(tmp_path):
    index = IndexMemoire()
    ingestion = IngestionDossier(_registre(), FauxEncodeur(), index)
    rapport = ingestion.ingerer(tmp_path)
    assert rapport.nb_chunks_indexes == 0
    assert index.taille() == 0


def test_ingestion_un_pdf_court(tmp_path):
    _make_pdf(tmp_path / "acte.pdf", "Un contrat court.")
    index = IndexMemoire()
    ingestion = IngestionDossier(_registre(), FauxEncodeur(), index)
    rapport = ingestion.ingerer(tmp_path)
    assert rapport.nb_fichiers_ok == 1
    assert rapport.nb_chunks_total >= 1
    assert index.taille() == rapport.nb_chunks_indexes


def test_ingestion_plusieurs_fichiers(tmp_path):
    _make_pdf(tmp_path / "a.pdf", "Contenu A.")
    _make_pdf(tmp_path / "b.pdf", "Contenu B.")
    index = IndexMemoire()
    ingestion = IngestionDossier(_registre(), FauxEncodeur(), index)
    rapport = ingestion.ingerer(tmp_path)
    assert rapport.nb_fichiers_ok == 2
    assert index.taille() >= 2


def test_ingestion_ignore_fichiers_non_supportes(tmp_path):
    _make_pdf(tmp_path / "ok.pdf", "Piece valide.")
    (tmp_path / "note.xyz").write_text("inconnu")
    index = IndexMemoire()
    ingestion = IngestionDossier(_registre(), FauxEncodeur(), index)
    rapport = ingestion.ingerer(tmp_path)
    assert rapport.nb_fichiers_ok == 1
    assert rapport.nb_fichiers_erreur == 1


def test_metadonnees_stockees(tmp_path):
    _make_pdf(tmp_path / "acte.pdf", "Un contenu simple.")
    index = IndexMemoire()
    ingestion = IngestionDossier(_registre(), FauxEncodeur(), index)
    ingestion.ingerer(tmp_path)
    res = index.rechercher([0.0] * 8, k=10)
    assert len(res) >= 1
    md = res[0].metadonnees
    assert md["source"] == "acte.pdf"
    assert md["longueur"] > 0


def test_identifiant_chunk_stable(tmp_path):
    _make_pdf(tmp_path / "acte.pdf", "Un contenu.")
    index = IndexMemoire()
    ingestion = IngestionDossier(_registre(), FauxEncodeur(), index)
    ingestion.ingerer(tmp_path)
    res = index.rechercher([0.0] * 8, k=10)
    ids = {r.id for r in res}
    assert any(i.startswith("acte.pdf#chunk_") for i in ids)


def test_encodeur_appele_une_fois(tmp_path):
    _make_pdf(tmp_path / "a.pdf", "Piece A.")
    _make_pdf(tmp_path / "b.pdf", "Piece B.")
    index = IndexMemoire()
    encodeur = FauxEncodeur()
    ingestion = IngestionDossier(_registre(), encodeur, index)
    ingestion.ingerer(tmp_path)
    assert len(encodeur.appels) == 1


def test_encodeur_incoherent_refuse(tmp_path):
    class MauvaisEncodeur:
        @property
        def dimension(self) -> int:
            return 8
        def encoder(self, textes: list[str]) -> list[list[float]]:
            return []

    _make_pdf(tmp_path / "a.pdf", "Piece A.")
    index = IndexMemoire()
    ingestion = IngestionDossier(_registre(), MauvaisEncodeur(), index)
    with pytest.raises(RuntimeError):
        ingestion.ingerer(tmp_path)