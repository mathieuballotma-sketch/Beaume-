"""Tests de profil_materiel.py — aucune dépendance modèle."""

import unittest

from profil_materiel import (
    ConfigurationRefusee,
    Materiel,
    MaterielInsuffisant,
    choisir_profil,
    detecter_materiel,
    qualifier,
)


def _mat(total_go, ncpu=10, arch="arm64", dispo_go=None):
    return Materiel(
        total_go=total_go, disponible_go=dispo_go, ncpu=ncpu,
        arch=arch, modele_mac="", systeme="macos",
    )


class TestQualification(unittest.TestCase):
    def test_8go_non_supporte(self):
        self.assertEqual(qualifier(_mat(8)), "non_supporte")

    def test_16go_apple_silicon_ok(self):
        self.assertEqual(qualifier(_mat(16)), "ok")

    def test_24go_apple_silicon_ok(self):
        self.assertEqual(qualifier(_mat(24)), "ok")

    def test_16go_intel_partiel(self):
        self.assertEqual(qualifier(_mat(16, arch="intel")), "support_partiel")


class TestChoixProfil(unittest.TestCase):
    def test_16go_contexte_2048(self):
        p = choisir_profil(_mat(16), taille_fichier_modele_go=2.0)
        self.assertEqual(p.contexte, 2048)
        self.assertEqual(p.n_gpu_layers, 99)
        self.assertEqual(p.statut_support, "ok")

    def test_24go_contexte_4096(self):
        p = choisir_profil(_mat(24), taille_fichier_modele_go=4.0)
        self.assertEqual(p.contexte, 4096)

    def test_32go_contexte_8192(self):
        p = choisir_profil(_mat(32), taille_fichier_modele_go=4.0)
        self.assertEqual(p.contexte, 8192)

    def test_8go_leve_materiel_insuffisant(self):
        with self.assertRaises(MaterielInsuffisant):
            choisir_profil(_mat(8), taille_fichier_modele_go=1.0)

    def test_modele_trop_gros_pour_16go(self):
        with self.assertRaises(ConfigurationRefusee):
            choisir_profil(_mat(16), taille_fichier_modele_go=10.0)

    def test_modele_raisonnable_pour_16go(self):
        p = choisir_profil(_mat(16), taille_fichier_modele_go=2.0)
        self.assertEqual(p.threads, 9)
        self.assertEqual(p.max_tokens, 512)

    def test_intel_pas_de_gpu_offload(self):
        p = choisir_profil(_mat(24, arch="intel"), taille_fichier_modele_go=2.0)
        self.assertEqual(p.n_gpu_layers, 0)
        self.assertEqual(p.statut_support, "support_partiel")
        self.assertIn("Intel", p.notes)

    def test_ram_disponible_insuffisante_refuse(self):
        with self.assertRaises(ConfigurationRefusee):
            choisir_profil(_mat(24, dispo_go=4.0), taille_fichier_modele_go=3.0)

    def test_ram_disponible_suffisante_accepte(self):
        p = choisir_profil(_mat(24, dispo_go=10.0), taille_fichier_modele_go=3.0)
        self.assertEqual(p.statut_support, "ok")

    def test_7b_sur_16go_ram_ok_accepte(self):
        p = choisir_profil(_mat(16, dispo_go=10.0), taille_fichier_modele_go=4.7)
        self.assertEqual(p.contexte, 2048)

    def test_7b_sur_16go_ram_serree_refuse(self):
        with self.assertRaises(ConfigurationRefusee):
            choisir_profil(_mat(16, dispo_go=5.0), taille_fichier_modele_go=4.7)

    def test_contexte_prefere_respecte(self):
        p = choisir_profil(
            _mat(24), taille_fichier_modele_go=2.0, contexte_prefere=16384,
        )
        self.assertEqual(p.contexte, 16384)
        self.assertEqual(p.max_tokens, 1024)


class TestDetectionReelle(unittest.TestCase):
    def test_detection_retourne_quelque_chose(self):
        m = detecter_materiel()
        self.assertGreater(m.total_go, 0.0)
        self.assertGreater(m.ncpu, 0)
        self.assertIn(m.arch, ("arm64", "intel", "inconnu"))
        print(f"\n  [info] RAM totale = {m.total_go} Go, ncpu = {m.ncpu}, "
              f"arch = {m.arch}, dispo = {m.disponible_go} Go")


if __name__ == "__main__":
    unittest.main(verbosity=2)
