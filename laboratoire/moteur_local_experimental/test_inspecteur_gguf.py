"""Tests de la fiche d'inspection ; aucun modèle ou réseau nécessaire."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from inspecteur_gguf import inspecter_modele, InspectionImpossible

class TestInspecteurGGUF(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'fixture.gguf'
        self.path.write_bytes(b'GGUFfixture')

    def lecteur(self, _):
        field = lambda x: SimpleNamespace(contents=lambda: x)
        return SimpleNamespace(fields={'general.architecture': field('qwen2'),
                                       'general.name': field('Fictif'),
                                       'qwen2.context_length': field(1024)},
                               tensors=[SimpleNamespace(n_elements=20),
                                        SimpleNamespace(n_elements=30)])

    def test_fiche_metadonnees_et_inconnues(self):
        r = inspecter_modele(self.path, lecteur=self.lecteur)
        self.assertEqual((r['architecture'], r['nom']), ('qwen2', 'Fictif'))
        self.assertEqual(r['elements_tenseurs'], 50)
        self.assertEqual(r['contexte_entraine_tokens'], 1024)
        self.assertIsNone(r['ram_inference_requise_octets'])
        self.assertIsNone(r['nombre_couches'])
        self.assertEqual(r['qualification_taches'], 'non_evaluee')

    def test_empreinte_sur_demande(self):
        r = inspecter_modele(self.path, empreinte=True, lecteur=self.lecteur)
        self.assertEqual(r['sha256'], hashlib.sha256(b'GGUFfixture').hexdigest())

    def test_fichier_invalide_ou_absent(self):
        self.path.write_bytes(b'pas GGUF')
        with self.assertRaises(InspectionImpossible): inspecter_modele(self.path, lecteur=self.lecteur)
        with self.assertRaises(InspectionImpossible): inspecter_modele(self.path.parent / 'absent', lecteur=self.lecteur)

    def test_lecteur_invalide(self):
        def invalide(_): raise ValueError('entete tronquee')
        with self.assertRaises(InspectionImpossible): inspecter_modele(self.path, lecteur=invalide)

if __name__ == '__main__': unittest.main()
