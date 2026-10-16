"""Adaptateur PDF : respecte le contrat Extracteur du port.

Utilise pymupdf pour extraire le texte d'un PDF natif (non scanne).

Chaque page est retournee avec son numero et ses offsets dans le
texte global, pour permettre la tracabilite des faits.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

from beaume.ports.extracteur import PageExtraite


def _extraire_pages(path: Path) -> list[PageExtraite]:
    """Extrait le texte page par page, avec offsets globaux."""
    chemin = Path(path)
    if not chemin.exists():
        raise FileNotFoundError(f"PDF introuvable : {chemin}")

    doc = pymupdf.open(chemin)
    pages: list[PageExtraite] = []
    offset = 0

    try:
        for i, page in enumerate(doc, start=1):
            texte = page.get_text()
            fin = offset + len(texte)
            pages.append(PageExtraite(
                numero=i,
                texte=texte,
                debut_car=offset,
                fin_car=fin,
            ))
            offset = fin + 2  # +2 pour le "\n\n" separateur
    finally:
        doc.close()

    return pages


class ExtracteurPDF:
    """Extracteur pour les fichiers .pdf (natifs, non scannes)."""

    def supporte(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def extraire(self, path: Path) -> str:
        """Retourne le texte concatene (interface historique)."""
        pages = _extraire_pages(path)
        return "\n\n".join(p.texte for p in pages)

    def extraire_avec_pages(self, path: Path) -> list[PageExtraite]:
        """Retourne les pages avec leurs offsets (nouvelle interface)."""
        return _extraire_pages(path)