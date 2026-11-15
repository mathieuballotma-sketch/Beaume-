"""Tests de detecter_dates.py."""
import unittest
from detecter_dates import detecter_dates_divergentes


def _aff(page, texte, date="inconnue"):
    return {"page": page, "texte": texte, "date": date}


class TestDatesDivergentes(unittest.TestCase):
    def test_deux_receptions_datesrentes(self):
        a = _aff(5, "Nordex confirme la reception du contrat pour le dossier 482",
                 date="2024-04-03")
        b = _aff(9, "Nordex confirme la reception du contrat pour le dossier 482",
                 date="2024-04-10")
        r = detecter_dates_divergentes([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["niveau"], "date_divergente")
        self.assertEqual(r[0]["date_a"], "2024-04-03")
        self.assertEqual(r[0]["date_b"], "2024-04-10")

    def test_objets_differents_pas_divergence(self):
        a = _aff(5, "Nordex confirme la reception du contrat pour le dossier 482",
                 date="2024-04-03")
        b = _aff(9, "Nordex confirme la reception de la facture pour le dossier 482",
                 date="2024-04-10")
        r = detecter_dates_divergentes([a, b])
        self.assertEqual(len(r), 0)

    def test_polarite_differente_pas_divergence_de_date(self):
        # reception positive vs negative : c'est une contradiction, pas une divergence de date
        a = _aff(9, "Nordex confirme la reception du contrat pour le dossier 482",
                 date="2024-04-03")
        b = _aff(17, "Nordex nie avoir recu le contrat pour le dossier 482",
                 date="2024-04-10")
        r = detecter_dates_divergentes([a, b])
        self.assertEqual(len(r), 0)

    def test_meme_date_pas_divergence(self):
        a = _aff(5, "Nordex confirme la reception du contrat pour le dossier 482",
                 date="2024-04-03")
        b = _aff(9, "Nordex confirme la reception du contrat pour le dossier 482",
                 date="2024-04-03")
        self.assertEqual(detecter_dates_divergentes([a, b]), [])

    def test_une_date_une_inconnue_signale_date_manquante(self):
        a = _aff(5, "Nordex confirme la reception du contrat pour le dossier 482",
                 date="2024-04-03")
        b = _aff(9, "Nordex confirme la reception du contrat pour le dossier 482",
                 date="inconnue")
        r = detecter_dates_divergentes([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["niveau"], "date_manquante")

    def test_deux_dates_inconnues_pas_signal(self):
        a = _aff(5, "Nordex confirme la reception du contrat pour le dossier 482")
        b = _aff(9, "Nordex confirme la reception du contrat pour le dossier 482")
        self.assertEqual(detecter_dates_divergentes([a, b]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
