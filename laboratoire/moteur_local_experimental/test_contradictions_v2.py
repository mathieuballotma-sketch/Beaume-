"""Tests detecter_contradictions v2 : contre-exemple contrat/facture."""
import unittest
from detecter_contradictions import detecter_contradictions


def _aff(page, texte):
    return {"page": page, "texte": texte}


class TestContreExemple(unittest.TestCase):
    def test_reception_contrat_vs_non_reception_facture(self):
        """Meme dossier 482, objets differents : ambigu, pas contradiction."""
        a = _aff(5, "Nordex confirme la reception du contrat pour le dossier 482")
        b = _aff(12, "Nordex nie avoir recu la facture pour le dossier 482")
        r = detecter_contradictions([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["niveau"], "ambigu")
        self.assertFalse(r[0]["meme_objet"])
        self.assertEqual(sorted(r[0]["objet_a"]), ["contrat"])
        self.assertEqual(sorted(r[0]["objet_b"]), ["facture"])
        self.assertIn("objets differents", r[0]["raison"])

    def test_reception_dossier_vs_non_reception_dossier(self):
        """Meme objet : contradiction certaine."""
        a = _aff(9, "Nordex confirme la reception du dossier pour le dossier 482")
        b = _aff(17, "Nordex nie avoir recu le dossier pour le dossier 482")
        r = detecter_contradictions([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["niveau"], "contradiction")
        self.assertTrue(r[0]["meme_objet"])

    def test_transfert_contrat_vs_non_reception_facture_ambigu(self):
        a = _aff(2, "Lina Morel remet le contrat pour le dossier 482")
        b = _aff(17, "Nordex nie avoir recu la facture pour le dossier 482")
        r = detecter_contradictions([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["niveau"], "ambigu")

    def test_un_objet_absent_des_deux_cotes_ambigu(self):
        """Aucun objet identifie des deux cotes : signal a examiner, pas certitude."""
        a = _aff(9, "Nordex confirme la reception pour le dossier 482")
        b = _aff(17, "Nordex nie avoir recu pour le dossier 482")
        r = detecter_contradictions([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["niveau"], "ambigu")
        self.assertFalse(r[0]["meme_objet"])

    def test_pas_de_signal_si_polarite_identique(self):
        a = _aff(9, "Nordex confirme la reception du contrat pour le dossier 482")
        b = _aff(10, "Nordex confirme la reception du contrat pour le dossier 482")
        self.assertEqual(detecter_contradictions([a, b]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
