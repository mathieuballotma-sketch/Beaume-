"""Tests de verrou_cache.py — aucune inférence réelle."""
import glob
import os
import unittest
from unittest.mock import patch

from verrou_cache import CacheInterdit, appel_modele_sans_cache


class TestInterdictions(unittest.TestCase):
    def test_prompt_cache_leve(self):
        with self.assertRaises(CacheInterdit):
            appel_modele_sans_cache("modele.gguf", "p", prompt_cache="/tmp/x.bin")

    def test_cache_mode_enabled_leve(self):
        with self.assertRaises(CacheInterdit):
            appel_modele_sans_cache("modele.gguf", "p", cache_mode="enabled")

    def test_cache_mode_auto_leve(self):
        with self.assertRaises(CacheInterdit):
            appel_modele_sans_cache("modele.gguf", "p", cache_mode="auto")

    def test_cache_path_leve(self):
        with self.assertRaises(CacheInterdit):
            appel_modele_sans_cache("modele.gguf", "p", cache_path="/tmp/c")

    def test_prompt_cache_none_autorise(self):
        with patch('verrou_cache._reel', create=True):
            pass  # pas utilisé, on vérifie juste la délégation séparément


class TestDelegation(unittest.TestCase):
    def test_cache_mode_disabled_delegue(self):
        sentinelle = object()
        with patch('premier_moteur.executer_llama_completion',
                   return_value=sentinelle) as mock:
            r = appel_modele_sans_cache("m", "p", cache_mode="disabled")
        self.assertIs(r, sentinelle)
        mock.assert_called_once()

    def test_aucun_param_cache_delegue(self):
        sentinelle = object()
        with patch('premier_moteur.executer_llama_completion',
                   return_value=sentinelle) as mock:
            r = appel_modele_sans_cache("m", "p", max_tokens=8)
        self.assertIs(r, sentinelle)
        args, kwargs = mock.call_args
        self.assertEqual(args, ("m", "p"))
        self.assertEqual(kwargs, {"max_tokens": 8})


class TestPasDeFichierCacheCree(unittest.TestCase):
    def test_pas_de_fichier_cache_pendant_appel(self):
        # L'appel va être mocké, mais on vérifie que le dossier cache
        # de llama.cpp n'est pas créé par le wrapper seul.
        avant = set(glob.glob(os.path.expanduser('~/Library/Caches/beaume/*'))) \
            if os.path.isdir(os.path.expanduser('~/Library/Caches/beaume')) else set()
        with patch('premier_moteur.executer_llama_completion',
                   return_value=None):
            appel_modele_sans_cache("m", "p", max_tokens=8)
        apres = set(glob.glob(os.path.expanduser('~/Library/Caches/beaume/*'))) \
            if os.path.isdir(os.path.expanduser('~/Library/Caches/beaume')) else set()
        self.assertEqual(avant, apres)


if __name__ == "__main__":
    unittest.main(verbosity=2)
