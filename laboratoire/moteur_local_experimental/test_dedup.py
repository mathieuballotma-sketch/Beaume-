"""Tests de dedup.py — dedoublonnage deterministe des affirmations.

La partie "ancrage" a migre vers ancrage.py et test_ancrage_v3.py (12 tests
plus complets : citation_litterale, approximative, negation_divergente,
non_retrouve, proximite de date).
"""
import unittest
from dedup import dedupliquer


class TestDedup(unittest.TestCase):
    def test_sous_chaine_garde_le_plus_long(self):
        court = {"texte": "Nordex affirme ne jamais avoir recu le dossier 482"}
        long_ = {"texte": "Le 12 avril 2024, Nordex affirme ne jamais avoir recu le dossier 482"}
        r = dedupliquer([court, long_])
        self.assertEqual(len(r), 1)
        self.assertIn("12 avril 2024", r[0]["texte"])

    def test_ordre_inverse_garde_long(self):
        long_ = {"texte": "Le 12 avril 2024, Nordex affirme ne jamais avoir recu le dossier 482"}
        court = {"texte": "Nordex affirme ne jamais avoir recu le dossier 482"}
        r = dedupliquer([long_, court])
        self.assertEqual(len(r), 1)
        self.assertIn("12 avril 2024", r[0]["texte"])

    def test_textes_differents_garde_les_deux(self):
        a = {"texte": "Lina remet le dossier 482 a Nordex"}
        b = {"texte": "Nordex nie avoir recu le dossier 482"}
        self.assertEqual(len(dedupliquer([a, b])), 2)

    def test_accents_ignores(self):
        a = {"texte": "Nordex confirme reception"}
        b = {"texte": "Nordex confirme réception"}
        r = dedupliquer([a, b])
        self.assertEqual(len(r), 1)

    def test_liste_vide(self):
        self.assertEqual(dedupliquer([]), [])

    def test_un_seul_element(self):
        a = {"texte": "Phrase unique"}
        self.assertEqual(len(dedupliquer([a])), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
