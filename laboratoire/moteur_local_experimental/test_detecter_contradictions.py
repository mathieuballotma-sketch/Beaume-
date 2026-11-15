"""Tests de detecter_contradictions.py."""
import unittest
from detecter_contradictions import detecter_contradictions, _polarite, _dossiers


class TestPolarite(unittest.TestCase):
    def test_reception_positive(self):
        self.assertEqual(
            _polarite("Nordex confirme par courriel la reception du dossier 482"),
            "reception_positive",
        )

    def test_reception_negative(self):
        self.assertEqual(
            _polarite("Nordex affirme ne jamais avoir recu le dossier 482"),
            "reception_negative",
        )

    def test_transfert_positif(self):
        self.assertEqual(
            _polarite("Lina Morel remet le dossier 482 a Nordex"),
            "transfert_positif",
        )

    def test_neutre(self):
        self.assertEqual(
            _polarite("Lina Morel demande une copie du courriel"),
            "neutre",
        )


class TestDossiers(unittest.TestCase):
    def test_482(self):
        self.assertEqual(_dossiers("le dossier bleu numero 482 a Nordex"), {"482"})

    def test_aucun(self):
        self.assertEqual(_dossiers("une phrase sans dossier"), set())


class TestContradictions(unittest.TestCase):
    def _aff(self, page, texte):
        return {"page": page, "texte": texte}

    def test_contradiction_directe(self):
        a = self._aff(9, "Nordex confirme la reception du dossier 482")
        b = self._aff(17, "Nordex nie avoir recu le dossier 482")
        r = detecter_contradictions([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["niveau"], "contradiction")
        self.assertEqual({r[0]["page_a"], r[0]["page_b"]}, {9, 17})

    def test_tension_transfert_vs_reception_neg(self):
        a = self._aff(2, "Lina Morel remet le dossier 482 a Nordex")
        b = self._aff(17, "Nordex nie avoir recu le dossier 482")
        r = detecter_contradictions([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["niveau"], "tension")

    def test_pas_de_contradiction_si_dossiers_differents(self):
        a = self._aff(9, "Nordex confirme la reception du dossier 111")
        b = self._aff(17, "Nordex nie avoir recu le dossier 482")
        self.assertEqual(len(detecter_contradictions([a, b])), 0)

    def test_pas_de_contradiction_si_meme_polarite(self):
        a = self._aff(9, "Nordex confirme la reception du dossier 482")
        b = self._aff(10, "Nordex confirme la reception du dossier 482")
        self.assertEqual(len(detecter_contradictions([a, b])), 0)

    def test_demande_ne_contredit_pas(self):
        a = self._aff(23, "Lina Morel demande une copie du courriel de reception")
        b = self._aff(17, "Nordex nie avoir recu le dossier 482")
        self.assertEqual(len(detecter_contradictions([a, b])), 0)

    def test_cas_reel_4_affirmations(self):
        affs = [
            self._aff(2, "Le 3 avril 2024, Lina Morel remet le dossier bleu numero 482 a Nordex."),
            self._aff(9, "Le 5 avril 2024, Nordex confirme par courriel la reception du dossier bleu numero 482."),
            self._aff(17, "Nordex affirme ne jamais avoir recu le dossier bleu numero 482."),
            self._aff(23, "Lina Morel demande une copie du courriel de reception du 5 avril 2024."),
        ]
        r = detecter_contradictions(affs)
        niveaux = sorted(x["niveau"] for x in r)
        self.assertEqual(niveaux, ["contradiction", "tension"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
