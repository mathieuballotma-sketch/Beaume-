"""Chronometrage du pipeline d'ingestion."""
from pathlib import Path
import shutil
import pymupdf

from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.application.ingestion import IngestionDossier
from beaume.config import paths
from beaume.ports.registre import RegistreExtracteurs
from beaume.testing.index_memoire import IndexMemoire
from beaume.utils.profiler import profil_actif


TEXTE = "Le present contrat est conclu entre les parties soussignees. " * 30


class FauxEncodeur:
    @property
    def dimension(self) -> int:
        return 8

    def encoder(self, textes):
        return [[float((hash(t) + i) % 100) for i in range(8)] for t in textes]


def _make_pdf(path, texte):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), texte[:2000], fontsize=10)
    doc.save(path)
    doc.close()


def main() -> int:
    dossier = paths.TMP / "profil_dossier"
    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)

    _make_pdf(dossier / "contrat.pdf", TEXTE)
    _make_pdf(dossier / "avenant.pdf", TEXTE[:1500])
    _make_pdf(dossier / "courrier.pdf", TEXTE[:800])

    registre = RegistreExtracteurs()
    registre.enregistrer(ExtracteurPDF())
    ingestion = IngestionDossier(registre, FauxEncodeur(), IndexMemoire())

    with profil_actif("ingestion") as p:
        r = ingestion.ingerer(dossier)

    print()
    print(f"Dossier  : {dossier}")
    print(f"Fichiers : {r.nb_fichiers_ok} ok, {r.nb_fichiers_erreur} erreurs")
    print(f"Chunks   : {r.nb_chunks_total} extraits, {r.nb_chunks_indexes} indexes")
    print()
    print(p.rapport())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
