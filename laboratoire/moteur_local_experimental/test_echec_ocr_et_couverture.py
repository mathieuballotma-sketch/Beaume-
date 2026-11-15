"""Tests corrections #2 et #3 : methode exposee, echec_ocr -> partiel, coords."""
import unittest
from pathlib import Path
from unittest.mock import patch

from cortex_minimal import executer_cortex


def _fake_inv_une_page_echec(chemin, pages=None, ocr_fallback=True):
    return {
        "piece": "x.pdf", "sha_piece": "abc",
        "passages": [
            {"page": 1, "texte": "", "methode_extraction": "echec_ocr:simulation",
             "coordonnees": None, "sha_piece": "abc", "piece": "x.pdf"},
            {"page": 2, "texte": "Le 3 avril 2024, Lina Morel remet le dossier 482",
             "methode_extraction": "pymupdf",
             "coordonnees": None, "sha_piece": "abc", "piece": "x.pdf"},
        ],
        "n_ocr": 0, "echecs_ocr": 1,
    }


def _fake_extraire_vide(passage, profil, modele):
    return {
        "etat": "ok",
        "affirmations_retenues": [],
        "affirmations_hors_condition": [],
        "affirmations_non_retrouvees_dans_page": [],
        "affirmations_approximatives": [],
        "affirmations_negation_divergente": [],
        "non_extraites": True,
        "duree_secondes": 0.0,
    }


class TestEchecOcrVisible(unittest.TestCase):
    def test_page_echec_ocr_donne_partiel(self):
        with patch("parcours_vertical_v1.inventaire_pdf", _fake_inv_une_page_echec), \
             patch("parcours_vertical_v1.extraire_affirmations", _fake_extraire_vide):
            r = executer_cortex(pdf=Path("/tmp/x.pdf"), pages=[1, 2])
        self.assertEqual(r["etat_global"], "partiel")
        self.assertEqual(r["couverture"]["pages_echec_ocr"], 1)
        self.assertEqual(r["couverture"]["pages_total"], 2)
        self.assertEqual(r["couverture"]["pages_lues"], 1)
        self.assertLess(r["couverture"]["ratio"], 1.0)
        p1 = [p for p in r["pages"] if p["page"] == 1][0]
        self.assertEqual(p1["statut"], "echec_ocr")
        self.assertIn("simulation", p1.get("methode_extraction", ""))


class TestMethodeExposee(unittest.TestCase):
    def test_pymupdf_expose_dans_resultat(self):
        with patch("parcours_vertical_v1.inventaire_pdf", _fake_inv_une_page_echec), \
             patch("parcours_vertical_v1.extraire_affirmations", _fake_extraire_vide):
            r = executer_cortex(pdf=Path("/tmp/x.pdf"), pages=[2])
        p2 = [p for p in r["pages"] if p["page"] == 2][0]
        self.assertEqual(p2["methode_extraction"], "pymupdf")
        self.assertIn("coordonnees", p2)


class TestCoordonneesOCR(unittest.TestCase):
    def test_ocr_retourne_bbox_sur_image_existante(self):
        import os
        img = "/tmp/page2_scannee.png"
        if not os.path.isfile(img):
            self.skipTest("image de test absente")
        from ocr_vision import ocr_image
        texte, bboxes = ocr_image(img, retour_coordonnees=True)
        self.assertGreater(len(texte), 20)
        self.assertGreater(len(bboxes), 0)
        b = bboxes[0]
        for k in ("confiance", "x", "y", "largeur", "hauteur", "texte"):
            self.assertIn(k, b)
        self.assertGreaterEqual(b["x"], 0.0)
        self.assertLessEqual(b["x"], 1.0)

    def test_ocr_sans_retour_coordonnees_reste_texte(self):
        import os
        img = "/tmp/page2_scannee.png"
        if not os.path.isfile(img):
            self.skipTest("image de test absente")
        from ocr_vision import ocr_image
        r = ocr_image(img)
        self.assertIsInstance(r, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
