"""Tests de parcours_vertical_v1.py."""
import unittest
from unittest.mock import patch

from parcours_vertical_v1 import (
    CORPUS_DEFAUT,
    MODELE_DEFAUT,
    PDF_DEFAUT,
    charger_corpus,
    executer_parcours,
    extraire_affirmations,
    inventaire_pdf,
    rapprocher,
)
from profil_materiel import Materiel, Profil

_MAT_SIMULE = None


def setUpModule():
    from unittest.mock import patch
    from profil_materiel import Materiel
    global _MAT_SIMULE
    _MAT_SIMULE = patch(
        "profil_materiel.detecter_materiel",
        return_value=Materiel(
            total_go=24.0, disponible_go=8.0, ncpu=10,
            arch="arm64", modele_mac="sim", systeme="macos",
        ),
    )
    _MAT_SIMULE.start()


def tearDownModule():
    if _MAT_SIMULE is not None:
        _MAT_SIMULE.stop()




CORPUS_TEST = [
    {"id": "L-482", "code": "FICTIF", "numero": "482",
     "titre": "Remise de dossier",
     "texte": "La remise d'un dossier numerote a une societe doit etre constatee par ecrit.",
     "version": "2024-01-01"},
    {"id": "L-PAIE", "code": "FICTIF", "numero": "PAIE-01",
     "titre": "Paiement des factures",
     "texte": "Le paiement des factures doit etre effectue dans un delai de trente jours.",
     "version": "2024-01-01"},
]


class TestRapprocher(unittest.TestCase):
    def test_remise_trouve_article(self):
        aff = {"texte": "Lina Morel remet le dossier bleu numero 482 a Nordex",
               "date": "2024-04-03", "personnes": "Lina Morel"}
        r = rapprocher(aff, CORPUS_TEST)
        self.assertIn(r["etat"], ("propose", "incertain"))
        if r["etat"] in ("propose", "incertain"):
            self.assertEqual(r["article"]["id"], "L-482")

    def test_paiement_manquant(self):
        aff = {"texte": "La facture numero 1200 est emise le 5 mai",
               "date": "2024-05-05", "personnes": "aucune"}
        r = rapprocher(aff, CORPUS_TEST)
        self.assertEqual(r["etat"], "manquant")

    def test_affirmation_vide(self):
        aff = {"texte": "", "date": "", "personnes": ""}
        r = rapprocher(aff, CORPUS_TEST)
        self.assertEqual(r["etat"], "affirmation_vide")


class TestInventairePDF(unittest.TestCase):
    def test_24_pages(self):
        if not PDF_DEFAUT.is_file():
            self.skipTest("PDF absent")
        inv = inventaire_pdf(PDF_DEFAUT)
        self.assertEqual(len(inv["passages"]), 24)
        self.assertGreater(len(inv["sha_piece"]), 32)

    def test_filtre_pages(self):
        if not PDF_DEFAUT.is_file():
            self.skipTest("PDF absent")
        inv = inventaire_pdf(PDF_DEFAUT, pages=[2])
        self.assertEqual(len(inv["passages"]), 1)
        self.assertEqual(inv["passages"][0]["page"], 2)




class TestPostFiltre(unittest.TestCase):
    def test_hors_condition_separe(self):
        aff = {"texte": "F-10", "date": "inconnue", "personnes": "aucune"}
        from parcours_vertical_v1 import _est_secondaire
        # coherent avec le filtre : date inconnue + personnes aucune
        self.assertTrue(_est_secondaire(aff))

    def test_fait_reel_retenu(self):
        aff = {"texte": "X", "date": "2024-04-03", "personnes": "Lina Morel"}
        from parcours_vertical_v1 import _est_secondaire
        self.assertFalse(_est_secondaire(aff))


class TestPromptStrict(unittest.TestCase):
    def test_prompt_interdit_descriptions(self):
        from parcours_vertical_v1 import PROMPT_AFFIRMATIONS
        self.assertIn('date explicite', PROMPT_AFFIRMATIONS)
        self.assertIn('personne nommee', PROMPT_AFFIRMATIONS)
        self.assertIn('liste vide', PROMPT_AFFIRMATIONS)


class TestExtraireFiller(unittest.TestCase):
    def test_filler_non_concret(self):
        passage = {"texte": "Le service conserve les notes dans une chemise.",
                   "page": 1, "piece": "p.pdf", "sha_piece": "x"}
        profil = Profil(contexte=2048, n_gpu_layers=99, threads=9,
                        max_tokens=256, statut_support="ok", notes="")
        r = extraire_affirmations(passage, profil, MODELE_DEFAUT)
        self.assertEqual(r["etat"], "non_concret")
        self.assertEqual(r["affirmations_retenues"], [])


class TestNonFauxPositif(unittest.TestCase):
    def test_description_ne_propose_pas_article_hors_sujet(self):
        aff = {"texte": "Le service conserve dans une chemise separee les notes "
                        "de correspondance relatives a la sequence numero 02.",
               "date": "inconnue", "personnes": "aucune"}
        r = rapprocher(aff, CORPUS_TEST)
        self.assertNotEqual(r["etat"], "propose",
            msg=f"description pure ne doitre 'propose', obtenu {r}")

    def test_fait_date_donne_au_moins_incertain(self):
        aff = {"texte": "Le 3 avril 2024, Lina Morel remet le dossier bleu "
                        "numero 482 a Nordex.",
               "date": "2024-04-03", "personnes": "Lina Morel; Nordex"}
        r = rapprocher(aff, CORPUS_TEST)
        self.assertIn(r["etat"], ("propose", "incertain"))


class TestMachineNonSupporte(unittest.TestCase):
    def test_8go_non_supporte(self):
        with patch("parcours_vertical_v1.detecter_materiel") as mock_detect:
            mock_detect.return_value = Materiel(
                total_go=8.0, disponible_go=2.0, ncpu=8,
                arch="arm64", modele_mac="M1", systeme="macos",
            )
            r = executer_parcours(pages=[2])
            self.assertEqual(r["etat_global"], "non_supporte")
            self.assertIn("8", r["raison"])


class TestNominalReel(unittest.TestCase):
    @unittest.skipUnless(
        PDF_DEFAUT.is_file() and MODELE_DEFAUT.is_file(),
        "PDF ou modele absent",
    )
    def test_page_2_traitee(self):
        r = executer_parcours(pages=[2])
        if r["etat_global"] == "non_supporte":
            self.skipTest(f"RAM insuffisante a cet instant : {r.get('raison', '')[:120]}")
        self.assertEqual(r["etat_global"], "ok")
        self.assertEqual(len(r["passages"]), 1)
        p = r["passages"][0]
        self.assertEqual(p["page"], 2)
        self.assertIn(p["etat"], (
            "ok", "vide", "non_concret", "erreur_json",
            "erreur_modele", "erreur_validation",
        ))
        for rp in p["rapprochements"]:
            self.assertIn(rp["rapprochement"]["etat"],
                          ("propose", "manquant", "affirmation_vide",
                           "incertain"))




class TestSecondaireJamaisPropose(unittest.TestCase):
    def test_description_generique_ne_propose_pas(self):
        # Cas réel observé : "La presence de cette feuille dans le dossier
        # ne confirme pas..." score 0.21 sur L-482 — ne doit pas être propose
        aff = {"texte": "La presence de cette feuille dans le dossier ne "
                        "confirme pas a elle seule les declarations des "
                        "personnes. Chaque point reste a verifier avec le "
                        "document qui le mentionne.",
               "date": "inconnue", "personnes": "aucune"}
        r = rapprocher(aff, CORPUS_TEST)
        self.assertNotEqual(r["etat"], "propose",
            msg=f"description avec secondaire=True proposée à tort : {r}")

    def test_fait_reel_reste_possible(self):
        aff = {"texte": "Le 3 avril 2024, Lina Morel remet le dossier bleu "
                        "numero 482 a Nordex.",
               "date": "2024-04-03", "personnes": "Lina Morel; Nordex"}
        r = rapprocher(aff, CORPUS_TEST)
        self.assertNotEqual(r["etat"], "manquant")

if __name__ == "__main__":
    unittest.main(verbosity=2)
