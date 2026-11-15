"""Tests ancrage v3 : 3 niveaux texte, negation, proximite date."""
import unittest
from ancrage import ancrer


class TestNiveauxTexte(unittest.TestCase):
    def test_citation_litterale(self):
        page = "Le 3 avril 2024, Lina Morel remet le dossier 482 a Nordex."
        aff = {"texte": "Le 3 avril 2024, Lina Morel remet le dossier 482 a Nordex.",
               "date": "2024-04-03"}
        r = ancrer(aff, page)
        self.assertEqual(r["texte_statut"], "citation_litterale")
        self.assertTrue(r["texte_retrouve_dans_page"])

    def test_correspondance_approximative(self):
        page = "Le dossier a ete remis par Lina Morel au representant de Nordex le 3 avril 2024."
        aff = {"texte": "Lina Morel a remis le dossier 482 a Nordex.",
               "date": "inconnue"}
        r = ancrer(aff, page)
        self.assertEqual(r["texte_statut"], "correspondance_approximative")
        self.assertFalse(r["texte_retrouve_dans_page"])
        self.assertGreaterEqual(r["texte_ratio"], 0.6)

    def test_negation_inversee(self):
        """Cas explicite demande : page affirme, affirmation nie."""
        page = "Nordex confirme avoir recu le dossier 482."
        aff = {"texte": "Nordex ne confirme pas avoir recu le dossier 482.",
               "date": "inconnue"}
        r = ancrer(aff, page)
        self.assertEqual(r["texte_statut"], "negation_divergente")
        self.assertFalse(r["texte_retrouve_dans_page"])

    def test_negation_inverse_sens(self):
        """Page nie, affirmation affirme."""
        page = "Nordex n'a pas recu le dossier 482."
        aff = {"texte": "Nordex a recu le dossier 482.",
               "date": "inconnue"}
        r = ancrer(aff, page)
        self.assertEqual(r["texte_statut"], "negation_divergente")

    def test_non_retrouve(self):
        page = "Phrase sans rapport avec le fait allegue."
        aff = {"texte": "Le chat de la voisine a mange la souris.",
               "date": "inconnue"}
        r = ancrer(aff, page)
        self.assertEqual(r["texte_statut"], "non_retrouve")
        self.assertFalse(r["texte_retrouve_dans_page"])


class TestDates(unittest.TestCase):
    def test_date_ancree_proche_extrait(self):
        page = ("Preamble sans date. Le 3 avril 2024, Lina Morel remet "
                "le dossier 482 a Nordex. Autre suite.")
        aff = {"texte": "Le 3 avril 2024, Lina Morel remet le dossier 482 a Nordex.",
               "date": "2024-04-03"}
        r = ancrer(aff, page)
        self.assertEqual(r["date_statut"], "ancree_proche_extrait")
        self.assertEqual(r["date"], "2024-04-03")
        self.assertTrue(r["date_association_verifiee"])

    def test_date_presente_mais_loin_de_l_extrait(self):
        """Date dans l'affirmation et dans la page, mais loin de l'extrait cite.
        Le statut doit signaler que l'association n'est pas verifiee."""
        page = ("Le 3 avril 2024, Lina Morel remet le dossier 111 a la societe Alpha. "
                + ("Filler text repeated for distance purposes only. " * 6)
                + "Un dossier 482 existe dans la page.")
        aff = {"texte": "Le 3 avril 2024, un dossier 482 existe dans la page.",
               "date": "2024-04-03"}
        r = ancrer(aff, page)
        self.assertEqual(r["date_statut"], "date_presente_ailleurs_dans_page")
        self.assertFalse(r["date_association_verifiee"])
        self.assertGreater(r["distance_caracteres"], 200)

    def test_date_non_ancree_dans_affirmation(self):
        page = "Le 3 avril 2024, Lina Morel remet le dossier 482."
        aff = {"texte": "Lina Morel remet le dossier 482.",
               "date": "2024-04-03"}
        r = ancrer(aff, page)
        self.assertEqual(r["date_statut"], "non_ancree_dans_affirmation")
        self.assertEqual(r["date"], "inconnue")
        self.assertEqual(r["date_proposee_modele"], "2024-04-03")

    def test_date_absente_de_page(self):
        page = "Nordex confirme la reception du dossier 482."
        aff = {"texte": "Le 3 avril 2024, Nordex confirme la reception du dossier 482.",
               "date": "2024-04-03"}
        r = ancrer(aff, page)
        self.assertEqual(r["date_statut"], "non_ancree_dans_page")
        self.assertEqual(r["date"], "inconnue")

    def test_date_inconnue(self):
        aff = {"texte": "Nordex confirme la reception.", "date": "inconnue"}
        r = ancrer(aff, "Nordex confirme la reception.")
        self.assertEqual(r["date_statut"], "inconnue")


if __name__ == "__main__":
    unittest.main(verbosity=2)
