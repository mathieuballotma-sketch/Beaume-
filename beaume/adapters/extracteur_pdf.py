"""Adaptateur PDF : respecte le contrat Extracteur du port.

Utilise pymupdf pour extraire le texte d'un PDF natif (non scanne).
"""
from pathlib import Path

import pymupdf


def _extraire_texte(path: Path) -> str:
    """Extrait le texte d'un PDF page par page.

    Retourne une chaine unique, pages separees par une ligne vide.
    Peut retourner une chaine vide si le PDF est un scan sans OCR.
    """
    chemin = Path(path)
    if not chemin.exists():
        raise FileNotFoundError(f"PDF introuvable : {chemin}")

    doc = pymupdf.open(chemin)
    try:
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()

    return "\n\n".join(pages)


class ExtracteurPDF:
    """Extracteur pour les fichiers .pdf (natifs, non scannes)."""

    def supporte(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def extraire(self, path: Path) -> str:
        return _extraire_texte(path)
