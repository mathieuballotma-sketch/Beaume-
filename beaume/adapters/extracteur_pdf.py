"""Adaptateur PDF : respecte le contrat Extracteur du port.

L'extraction bas niveau vit dans beaume/extraction/pdf.py.
Ici on ne fait que l'adapter au contrat du port.
"""
from pathlib import Path

from beaume.extraction.pdf import extract_pdf_text


class ExtracteurPDF:
    """Extracteur pour les fichiers .pdf (natifs, non scannes)."""

    def supporte(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def extraire(self, path: Path) -> str:
        return extract_pdf_text(path)
