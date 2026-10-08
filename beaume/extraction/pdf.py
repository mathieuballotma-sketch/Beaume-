"""Extraction de texte depuis un PDF natif (non scanne).

Utilise l'API moderne pymupdf (remplace l'ancien module fitz).
"""
from pathlib import Path
import pymupdf


def extract_pdf_text(path: Path) -> str:
    """Extrait le texte d'un PDF page par page.

    Retourne une chaine unique, pages separees par une ligne vide.
    Peut retourner une chaine vide si le PDF est un scan sans OCR.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF introuvable : {path}")

    doc = pymupdf.open(path)
    try:
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()

    return "\n\n".join(pages)
