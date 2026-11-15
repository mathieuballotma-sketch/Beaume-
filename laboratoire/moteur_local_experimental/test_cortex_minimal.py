"""Tests de cortex_minimal.py."""

import unittest
from unittest.mock import patch

from cortex_minimal import Journal, executer_cortex

_MAT_SIMULE = None


def setUpModule():
    from unittest.mock import patch
    global _MAT_SIMULE
    from profil_materiel import Materiel
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





class TestJournal(unittest.TestCase):
    def test_mesure_une_etape(self):
        j = Journal()
        import time
        with j.mesurer("e1") as etat:
            time.sleep(0.01)
            etat["details"]["n"] = 42
        self.assertEqual(len(j.etapes), 1)
        e = j.etapes[0]
        self.assertEqual(e.nom, "e1")
        self.assertGreater(e.duree_s, 0)
        self.assertEqual(e.statut, "ok")
        self.assertEqual(e.details["n"], 42)

    def test_erreur_capturee(self):
        j = Journal()
        with self.assertRaises(RuntimeError):
            with j.mesurer("e1"):
                raise RuntimeError("boum")
        self.assertEqual(j.etapes[0].statut, "erreur")
        self.assertIn("boum", j.etapes[0].details["erreur"])

    def test_serialiser(self):
        j = Journal()
        j.ajouter("a", "ok", {"x": 1})
        d = j.serialiser()
        self.assertEqual(d[0]["nom"], "a")
        self.assertEqual(d[0]["details"]["x"], 1)


class TestRepriseSurErreur(unittest.TestCase):
    def test_echec_page_2_ne_bloque_pas_page_3(self):
        appels = {"n": 0}
        def fake_extraire(passage, profil, modele):
            appels["n"] += 1
            if passage["page"] == 2:
                raise RuntimeError("panne simulee")
            return {"etat": "ok", "affirmations_retenues": [],
                    "affirmations_hors_condition": [],
                    "affirmations_non_retrouvees_dans_page": [],
                    "non_extraites": False, "duree_secondes": 0.1}
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2, 3])
        self.assertEqual(r["etat_global"], "partiel")
        statuts = [p["statut"] for p in r["pages"]]
        self.assertEqual(statuts, ["erreur", "ok"])
        self.assertEqual(appels["n"], 2)

    def test_page_non_concret_est_skipped(self):
        """Ancien nom 'non_concret' remplace par 'non_extraites' (correction 2)."""
        def fake_extraire(passage, profil, modele):
            return {"etat": "vide", "raison": "aucune date detectee",
                    "non_extraites": True}
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2, 3])
        self.assertEqual(r["etat_global"], "ok")
        self.assertEqual([p["statut"] for p in r["pages"]],
                         ["non_extraites", "non_extraites"])


    def test_contradictions_dans_resultat(self):
        """Le resultat doit exposer un champ contradictions (liste)."""
        def fake_extraire(passage, profil, modele):
            return {"etat": "ok", "affirmations_retenues": [],
                    "affirmations_hors_condition": [],
                    "affirmations_non_retrouvees_dans_page": [],
                    "non_extraites": False, "duree_secondes": 0.0}
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2])
        self.assertIn("contradictions", r)
        self.assertIsInstance(r["contradictions"], list)


    def test_dates_divergentes_present(self):
        def fake_extraire(passage, profil, modele):
            return {"etat": "ok", "affirmations_retenues": [],
                    "affirmations_hors_condition": [],
                    "affirmations_non_retrouvees_dans_page": [],
                    "non_extraites": False, "duree_secondes": 0.0}
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2])
        self.assertIn("dates_divergentes", r)
        self.assertIsInstance(r["dates_divergentes"], list)

class TestJournalDansPipeline(unittest.TestCase):
    def test_journal_contient_les_5_etapes_clefs(self):
        def fake_extraire(passage, profil, modele):
            return {"etat": "ok", "affirmations_retenues": [],
                    "affirmations_hors_condition": [],
                    "affirmations_non_retrouvees_dans_page": [],
                    "non_extraites": False, "duree_secondes": 0.0}
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2, 3])
        noms = [e["nom"] for e in r["journal"]]
        for attendu in ("detection_materiel", "inventaire_pdf",
                        "charger_corpus", "cycle_vie_modele",
                        "page_2", "page_3"):
            self.assertIn(attendu, noms)




class TestEtatsExplicites(unittest.TestCase):
    def test_erreur_modele_donne_partiel(self):
        def fake_extraire(passage, profil, modele):
            if passage["page"] == 2:
                return {"etat": "erreur_modele", "raison": "boum",
                        "duree_secondes": 0.1}
            return {"etat": "ok", "affirmations_retenues": [],
                    "affirmations_hors_condition": [],
                    "affirmations_non_retrouvees_dans_page": [],
                    "non_extraites": False, "duree_secondes": 0.1}
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2, 3])
        self.assertEqual(r["etat_global"], "partiel")
        statuts = [p["statut"] for p in r["pages"]]
        self.assertIn("erreur_modele", statuts)
        self.assertIn("ok", statuts)

    def test_erreur_json_donne_partiel(self):
        def fake_extraire(passage, profil, modele):
            return {"etat": "erreur_json", "raison": "json invalide",
                    "duree_secondes": 0.1}
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2])
        self.assertEqual(r["etat_global"], "partiel")
        self.assertEqual(r["pages"][0]["statut"], "erreur_json")

    def test_non_extraites_distinct_de_hors_condition(self):
        def fake_extraire(passage, profil, modele):
            return {"etat": "vide", "non_extraites": True,
                    "duree_secondes": 0.0}
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2])
        self.assertEqual(r["pages"][0]["statut"], "non_extraites")
        # Ce n'est pas une erreur : etat_global ok
        self.assertEqual(r["etat_global"], "ok")

    def test_page_conserve_retenues_et_hors_condition(self):
        def fake_extraire(passage, profil, modele):
            return {
                "etat": "ok",
                "affirmations_retenues": [{"texte": "fait", "date": "2024-04-03",
                                            "personnes": "Nordex", "date_ancree": True}],
                "affirmations_hors_condition": [{"texte": "desc", "hors_condition": True}],
                "affirmations_non_retrouvees_dans_page": [],
                "non_extraites": False, "duree_secondes": 0.1,
            }
        with patch("parcours_vertical_v1.extraire_affirmations", fake_extraire):
            r = executer_cortex(pages=[2])
        pg = r["pages"][0]
        self.assertEqual(len(pg["affirmations_retenues"]), 1)
        self.assertEqual(len(pg["affirmations_hors_condition"]), 1)


class TestPageIllisible(unittest.TestCase):
    def test_pdf_inexistant_donne_echec(self):
        from pathlib import Path
        r = executer_cortex(pdf=Path("/tmp/inexistant_xyz.pdf"), pages=[1])
        self.assertEqual(r["etat_global"], "echec")
        self.assertIn("raison", r)



if __name__ == "__main__":
    unittest.main(verbosity=2)
