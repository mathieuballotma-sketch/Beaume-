"""Tests ocr_backend.py."""
import platform
import unittest
from unittest.mock import patch

from ocr_backend import (
    OCRIndisponible,
    TesseractBackend,
    VisionBackend,
    backend_par_defaut,
    ocr_image_par_defaut,
)


class TestVisionBackend(unittest.TestCase):
    def test_disponible_sur_macos_avec_binaire(self):
        if platform.system() != "Darwin":
            self.skipTest("non macOS")
        self.assertTrue(VisionBackend().disponible())

    def test_indisponible_si_binaire_absent(self):
        with patch("pathlib.Path.is_file", return_value=False):
            self.assertFalse(VisionBackend().disponible())

    def test_ocr_image_sur_image_test(self):
        import os
        if not os.path.isfile("/tmp/page2_scannee.png"):
            self.skipTest("image test absente")
        v = VisionBackend()
        if not v.disponible():
            self.skipTest("Vision indisponible")
        texte, bboxes = v.ocr_image("/tmp/page2_scannee.png", retour_coordonnees=True)
        self.assertGreater(len(texte), 20)
        self.assertGreater(len(bboxes), 0)


class TestTesseractBackend(unittest.TestCase):
    def test_jamais_disponible_dans_ce_lot(self):
        self.assertFalse(TesseractBackend().disponible())

    def test_leve_ocr_indisponible(self):
        with self.assertRaises(OCRIndisponible):
            TesseractBackend().ocr_image("/tmp/x.png")


class TestBackendParDefaut(unittest.TestCase):
    def test_retourne_vision_sur_macos(self):
        if platform.system() != "Darwin":
            self.skipTest("non macOS")
        b = backend_par_defaut()
        if b is None:
            self.skipTest("aucun backend disponible")
        self.assertEqual(b.nom, "vision")

    def test_aucun_backend_leve(self):
        with patch.object(VisionBackend, "disponible", return_value=False):
            with patch.object(TesseractBackend, "disponible", return_value=False):
                with self.assertRaises(OCRIndisponible):
                    ocr_image_par_defaut("/tmp/x.png")


if __name__ == "__main__":
    unittest.main(verbosity=2)
