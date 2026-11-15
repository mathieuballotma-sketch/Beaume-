"""ocr_backend.py — Interface commune pour les moteurs OCR locaux.

Cette interface est posee pour permettre plusieurs implementations. Une
seule existe aujourd'hui : Vision Apple (macOS). Tesseract (Linux/Windows)
et un backend Windows natif restent a implementer, sans installation ni
telechargement implicite.

Chaque backend doit :
- refuser explicitement s il n est pas disponible sur la plateforme
- retourner (texte, bboxes) ; bboxes peut etre None si non disponible
- ne pas se rabattre silencieusement sur un autre moteur
"""
from __future__ import annotations
import platform
from typing import Optional


class OCRIndisponible(RuntimeError):
    """Le backend OCR n est pas disponible sur cette plateforme."""


class OCRBackend:
    nom = "abstrait"
    plateforme_supportee = "inconnue"

    def disponible(self) -> bool:
        return False

    def ocr_image(self, chemin_image: str, retour_coordonnees: bool = False):
        raise OCRIndisponible(
            "backend " + self.nom + " non implemente pour " + self.plateforme_supportee
        )

    def ocr_page(self, fitz_page, dpi: int = 200, retour_coordonnees: bool = False):
        raise OCRIndisponible(
            "backend " + self.nom + " ne sait pas lire une page PyMuPDF directement"
        )


class VisionBackend(OCRBackend):
    nom = "vision"
    plateforme_supportee = "macOS"

    def disponible(self) -> bool:
        if platform.system() != "Darwin":
            return False
        import pathlib
        return (pathlib.Path(__file__).parent / "bin" / "vision_ocr").is_file()

    def ocr_image(self, chemin_image, retour_coordonnees=False):
        if not self.disponible():
            raise OCRIndisponible(
                "Vision indisponible : plateforme " + platform.system()
                + " ou binaire bin/vision_ocr absent"
            )
        from ocr_vision import ocr_image as _v
        return _v(chemin_image, retour_coordonnees=retour_coordonnees)

    def ocr_page(self, fitz_page, dpi=200, retour_coordonnees=False):
        if not self.disponible():
            raise OCRIndisponible("Vision indisponible")
        from ocr_vision import ocr_page_image as _v
        return _v(fitz_page, dpi=dpi, retour_coordonnees=retour_coordonnees)


class TesseractBackend(OCRBackend):
    nom = "tesseract"
    plateforme_supportee = "multi (non implemente)"

    def disponible(self) -> bool:
        return False


_BACKENDS = (VisionBackend(), TesseractBackend())


def backend_par_defaut() -> Optional[OCRBackend]:
    for b in _BACKENDS:
        if b.disponible():
            return b
    return None


def ocr_image_par_defaut(chemin_image, retour_coordonnees=False):
    b = backend_par_defaut()
    if b is None:
        raise OCRIndisponible("aucun backend OCR disponible sur cette plateforme")
    return b.ocr_image(chemin_image, retour_coordonnees=retour_coordonnees)
