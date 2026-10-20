"""Tests du parcours de dossier client."""
from pathlib import Path
import pymupdf
import pytest

from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.application.lecteur_dossier import LecteurDossier
from beaume.ports.registre import RegistreExtracteurs


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


def test_dossier_inexistant(tmp_path):
    lecteur = LecteurDossier(_registre())
    with pytest.raises(NotADirectoryError):
        lecteur.lire(tmp_path / "absent")


def test_dossier_vide(tmp_path):
    lecteur = LecteurDossier(_registre())
    r = lecteur.lire(tmp_path)
    assert r.nb_ok == 0
    assert r.nb_erreurs == 0
    assert r.fin is not None


def test_dossier_avec_pdf(tmp_path):
    _make_pdf(tmp_path / "acte.pdf", "Acte de vente du 1er janvier.")
    lecteur = LecteurDossier(_registre())
    r = lecteur.lire(tmp_path)
    assert r.nb_ok == 1
    assert r.nb_erreurs == 0
    assert "Acte de vente" in r.fichiers[0].texte


def test_dossier_multi_fichiers(tmp_path):
    _make_pdf(tmp_path / "a.pdf", "Piece A")
    _make_pdf(tmp_path / "b.pdf", "Piece B")
    (tmp_path / "notes.xyz").write_text("inconnu")
    lecteur = LecteurDossier(_registre())
    r = lecteur.lire(tmp_path)
    assert r.nb_ok == 2
    assert r.nb_erreurs == 1


def test_ignore_fichiers_caches(tmp_path):
    _make_pdf(tmp_path / "visible.pdf", "Visible")
    (tmp_path / ".DS_Store").write_text("cache")
    lecteur = LecteurDossier(_registre())
    r = lecteur.lire(tmp_path)
    assert r.nb_ok == 1
    assert r.nb_erreurs == 0


def test_ordre_alphabetique(tmp_path):
    _make_pdf(tmp_path / "c.pdf", "C")
    _make_pdf(tmp_path / "a.pdf", "A")
    _make_pdf(tmp_path / "b.pdf", "B")
    lecteur = LecteurDossier(_registre())
    r = lecteur.lire(tmp_path)
    noms = [f.chemin.name for f in r.fichiers]
    assert noms == ["a.pdf", "b.pdf", "c.pdf"]


# --- Integration du chunking -------------------------------------------------

def test_texte_long_produit_plusieurs_chunks(tmp_path):
    texte = "\n\n".join(
        f"Paragraphe {i} avec un contenu suffisamment long pour peser."
        for i in range(20)
    )
    _make_pdf(tmp_path / "long.pdf", texte)
    lecteur = LecteurDossier(_registre(), taille_chunk=200, chevauchement=30)
    r = lecteur.lire(tmp_path)
    assert r.nb_ok == 1
    assert len(r.fichiers[0].chunks) > 1
    assert r.nb_chunks > 1


def test_texte_court_produit_un_chunk(tmp_path):
    _make_pdf(tmp_path / "court.pdf", "Un petit paragraphe.")
    lecteur = LecteurDossier(_registre())
    r = lecteur.lire(tmp_path)
    assert len(r.fichiers[0].chunks) == 1


def test_fichier_en_erreur_sans_chunk(tmp_path):
    (tmp_path / "notes.xyz").write_text("inconnu")
    lecteur = LecteurDossier(_registre())
    r = lecteur.lire(tmp_path)
    f = r.fichiers[0]
    assert not f.ok
    assert f.chunks == ()
    assert r.nb_chunks == 0


def test_chunks_immuables(tmp_path):
    """FichierExtrait est frozen : chunks est un tuple, pas une liste."""
    _make_pdf(tmp_path / "a.pdf", "Contenu.")
    lecteur = LecteurDossier(_registre())
    r = lecteur.lire(tmp_path)
    assert isinstance(r.fichiers[0].chunks, tuple)


def test_logs_ne_contiennent_ni_nom_client_ni_message_d_erreur(tmp_path, caplog):
    nom_confidentiel = "CLIENT_CONFIDENTIEL.pdf"
    (tmp_path / nom_confidentiel).write_bytes(b"pdf factice")

    class ExtracteurEnErreur:
        def extraire_avec_pages(self, fichier):
            raise RuntimeError("CONTENU_CLIENT_CONFIDENTIEL")

    class Registre:
        def pour(self, fichier):
            return ExtracteurEnErreur()

    lecteur = LecteurDossier(Registre())
    lecteur.lire(tmp_path)

    assert nom_confidentiel not in caplog.text
    assert "CONTENU_CLIENT_CONFIDENTIEL" not in caplog.text
    assert "RuntimeError" in caplog.text
