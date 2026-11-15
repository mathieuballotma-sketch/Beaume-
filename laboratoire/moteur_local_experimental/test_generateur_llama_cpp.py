"""Tests de l'adaptateur GenerateurLlamaCpp — appels au modèle simulés."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from generateur_llama_cpp import (
    GenerateurLlamaCpp,
    ReponseLLM,
    _extraire_json,
    _extraire_tokens,
)
from premier_moteur import MARQUEUR_FIN
from schema_beaume import SchemaNonSupporte


SCHEMA_BEAUME = {
    "type": "object",
    "properties": {
        "contexte": {"type": "string"},
        "parties": {"type": "array", "items": {"type": "string"}},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "enum": ["A1", "A2"]},
                    "fichier": {"type": "string", "enum": ["d.pdf"]},
                    "pages": {
                        "type": "array",
                        "items": {"type": "integer", "enum": [1, 2, 3]},
                        "minItems": 1,
                        "maxItems": 3,
                        "uniqueItems": True,
                    },
                },
                "required": ["article_id", "fichier", "pages"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["contexte", "citations"],
    "additionalProperties": False,
}


class _Base(unittest.TestCase):
    def setUp(self):
        fd, self.chemin_modele = tempfile.mkstemp(suffix=".gguf")
        os.write(fd, b"dummy")
        os.close(fd)
        self.addCleanup(os.unlink, self.chemin_modele)
        p = patch("premier_moteur.shutil.which",
                  return_value="/fake/llama-completion")
        p.start()
        self.addCleanup(p.stop)


def _simuler(stdout, returncode=0, stderr=""):
    proc = MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)
    return patch("premier_moteur.subprocess.run", return_value=proc)


class TestContrat(_Base):
    def test_nom_modele_retourne_chemin(self):
        g = GenerateurLlamaCpp(self.chemin_modele)
        self.assertEqual(g.nom_modele(), os.path.realpath(self.chemin_modele))

    def test_generer_retourne_reponse_llm(self):
        brut = ('{"contexte": "a", "citations": []} ' + MARQUEUR_FIN)
        stderr = ("prompt eval time = 100.0 ms / 30 tokens\n"
                  "eval time = 200.0 ms / 15 runs\n")
        with _simuler(brut, stderr=stderr):
            g = GenerateurLlamaCpp(self.chemin_modele, max_tokens=50)
            r = g.generer("p", temperature=0.0, format=SCHEMA_BEAUME)
        self.assertIsInstance(r, ReponseLLM)
        self.assertIsInstance(r.texte, str)
        self.assertEqual(r.modele, os.path.realpath(self.chemin_modele))
        self.assertGreaterEqual(r.duree_s, 0.0)
        self.assertEqual(r.tokens_prompt, 30)
        self.assertEqual(r.tokens_reponse, 15)

    def test_generer_sans_format(self):
        with _simuler("Orion\n"):
            g = GenerateurLlamaCpp(self.chemin_modele)
            r = g.generer("p", temperature=0.0)
        self.assertIsInstance(r, ReponseLLM)
        self.assertIsNone(g.derniere_validation())

    def test_format_str_refuse(self):
        g = GenerateurLlamaCpp(self.chemin_modele)
        with self.assertRaises(SchemaNonSupporte):
            g.generer("p", format="json")


class TestHelpers(unittest.TestCase):
    def test_extraire_json_retire_marqueur(self):
        self.assertEqual(
            _extraire_json('{"a": 1} ' + MARQUEUR_FIN),
            '{"a": 1}',
        )

    def test_extraire_json_sans_marqueur(self):
        self.assertEqual(_extraire_json('{"a": 1}'), '{"a": 1}')

    def test_tokens_absents(self):
        self.assertEqual(_extraire_tokens(""), (None, None))
        self.assertEqual(_extraire_tokens("rien"), (None, None))


class TestQuatreNiveaux(_Base):
    """Vérifie que les quatre niveaux restent distincts."""

    def test_succes_complet(self):
        brut = (
            '{"contexte": "a", "citations": [{"article_id": "A1", '
            '"fichier": "d.pdf", "pages": [1, 2]}]} ' + MARQUEUR_FIN
        )
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        v = g.derniere_validation()
        self.assertTrue(v.json_parse_valide)
        self.assertTrue(v.schema_technique_valide)
        self.assertIsNone(v.schema_metier_valide)

    def test_json_tronque(self):
        with _simuler('{"contexte": "a", "citations": ['):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        v = g.derniere_validation()
        self.assertFalse(v.json_parse_valide)
        self.assertFalse(v.schema_technique_valide)

    def test_pages_dupliquees_uniqueitems(self):
        brut = (
            '{"contexte": "a", "citations": [{"article_id": "A1", '
            '"fichier": "d.pdf", "pages": [1, 1]}]} ' + MARQUEUR_FIN
        )
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        v = g.derniere_validation()
        self.assertTrue(v.json_parse_valide)
        self.assertFalse(v.schema_technique_valide)
        self.assertTrue(any("uniqueItems" in x for x in v.violations))

    def test_article_hors_enum(self):
        brut = (
            '{"contexte": "a", "citations": [{"article_id": "ZZ", '
            '"fichier": "d.pdf", "pages": [1]}]} ' + MARQUEUR_FIN
        )
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        v = g.derniere_validation()
        self.assertFalse(v.schema_technique_valide)

    def test_champs_optionnels_absents(self):
        brut = '{"contexte": "a", "citations": []} ' + MARQUEUR_FIN
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        v = g.derniere_validation()
        self.assertTrue(v.schema_technique_valide)


class TestEchecs(_Base):
    def test_erreur_moteur_pas_de_validation(self):
        with _simuler("", returncode=1, stderr="load failed"):
            g = GenerateurLlamaCpp(self.chemin_modele)
            r = g.generer("p", format=SCHEMA_BEAUME)
        self.assertEqual(r.texte, "")
        self.assertIsNone(g.derniere_validation())

    def test_schema_non_supporte_leve(self):
        schema_bad = {"type": "object", "properties": {}, "weird": True}
        g = GenerateurLlamaCpp(self.chemin_modele)
        with self.assertRaises(SchemaNonSupporte):
            g.generer("p", format=schema_bad)

    def test_modele_absent(self):
        g = GenerateurLlamaCpp("/tmp/inexistant.gguf")
        r = g.generer("p")
        self.assertEqual(r.texte, "")


class TestEchecExplicite(_Base):
    """Une sortie invalide ne doit pas être transmise comme valide."""

    def test_echec_processus_avec_stdout_partiel(self):
        with _simuler('{"contexte": "a"', returncode=1,
                      stderr="crash apres debut"):
            g = GenerateurLlamaCpp(self.chemin_modele)
            r = g.generer("p", format=SCHEMA_BEAUME)
        self.assertEqual(r.texte, "")
        self.assertIsNone(g.derniere_validation())

    def test_json_tronque_texte_vide(self):
        with _simuler('{"contexte": "a", "citations": ['):
            g = GenerateurLlamaCpp(self.chemin_modele)
            r = g.generer("p", format=SCHEMA_BEAUME)
        self.assertEqual(r.texte, "")
        v = g.derniere_validation()
        self.assertIsNotNone(v)
        self.assertFalse(v.json_parse_valide)


class TestEchecExpliciteSuite(_Base):
    def test_uniqueitems_viole_texte_vide(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "d.pdf", "pages": [1, 1]}]} ' + MARQUEUR_FIN)
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            r = g.generer("p", format=SCHEMA_BEAUME)
        self.assertEqual(r.texte, "")
        v = g.derniere_validation()
        self.assertTrue(v.json_parse_valide)
        self.assertFalse(v.schema_technique_valide)
        self.assertTrue(any("uniqueItems" in x for x in v.violations))

    def test_succes_texte_conserve(self):
        brut = ('{"contexte": "a", "citations": []} ' + MARQUEUR_FIN)
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            r = g.generer("p", format=SCHEMA_BEAUME)
        self.assertNotEqual(r.texte, "")
        v = g.derniere_validation()
        self.assertTrue(v.schema_technique_valide)

    def test_appelant_production_recoit_erreur(self):
        """Simule _extraire_json de production : texte vide -> erreur."""
        import json
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "d.pdf", "pages": [1, 1]}]} ' + MARQUEUR_FIN)
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            r = g.generer("p", format=SCHEMA_BEAUME)
        with self.assertRaises(ValueError):
            if not r.texte:
                raise ValueError("Reponse LLM vide")
            json.loads(r.texte)


class TestPreparationSecurisee(_Base):
    """Bug signalé : mkstemp avant try/finally laissait un fichier orphelin."""

    def test_echec_fdopen_pas_d_orphelin(self):
        captures = {}
        real = tempfile.mkstemp
        def cap(prefix, suffix):
            c = real(prefix=prefix, suffix=suffix)
            captures["c"] = c[1]
            return c
        with patch("generateur_llama_cpp.tempfile.mkstemp", side_effect=cap):
            with patch("generateur_llama_cpp.os.fdopen",
                       side_effect=OSError("fdopen fail")):
                g = GenerateurLlamaCpp(self.chemin_modele)
                r = g.generer("p", format=SCHEMA_BEAUME)
        self.assertEqual(r.texte, "")
        self.assertFalse(os.path.exists(captures["c"]))
        d = g.dernier_diagnostic()
        self.assertIsNotNone(d)
        self.assertFalse(d.ok)
        self.assertEqual(d.cause, "preparation_grammaire")


class TestDiagnostic(_Base):
    def test_processus_echoue(self):
        with _simuler("", returncode=1, stderr="boom"):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        d = g.dernier_diagnostic()
        self.assertEqual(d.cause, "processus")
        self.assertFalse(d.processus_termine)
        self.assertIn("boom", d.erreur_moteur or "")

    def test_json_invalide(self):
        with _simuler('{"contexte": "a"'):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        d = g.dernier_diagnostic()
        self.assertEqual(d.cause, "json_invalide")
        self.assertTrue(d.processus_termine)
        self.assertFalse(d.json_parse_valide)

    def test_schema_invalide(self):
        brut = ('{"contexte": "a", "citations": [{"article_id": "A1", '
                '"fichier": "d.pdf", "pages": [1, 1]}]} ' + MARQUEUR_FIN)
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        d = g.dernier_diagnostic()
        self.assertEqual(d.cause, "schema_invalide")
        self.assertTrue(d.json_parse_valide)
        self.assertFalse(d.schema_technique_valide)
        self.assertTrue(any("uniqueItems" in x for x in d.violations))

    def test_succes(self):
        brut = '{"contexte": "a", "citations": []} ' + MARQUEUR_FIN
        with _simuler(brut):
            g = GenerateurLlamaCpp(self.chemin_modele)
            g.generer("p", format=SCHEMA_BEAUME)
        d = g.dernier_diagnostic()
        self.assertTrue(d.ok)
        self.assertIsNone(d.cause)


class TestPromptCache(_Base):
    def test_defaut_desactive(self):
        g = GenerateurLlamaCpp(self.chemin_modele)
        self.assertIsNone(g._prompt_cache)
        self.assertIsNone(g._cache_store)

    def test_prompt_cache_explicite_conserve(self):
        g = GenerateurLlamaCpp(
            self.chemin_modele, prompt_cache="/tmp/mon_cache.bin"
        )
        self.assertEqual(g._prompt_cache, "/tmp/mon_cache.bin")
        self.assertIsNone(g._cache_store)

    def test_cache_prefixe_active_cachestore(self):
        g = GenerateurLlamaCpp(
            self.chemin_modele,
            cache_prefixe="regle fixe fictive",
            cache_mode="enabled",
        )
        self.assertIsNotNone(g._cache_store)
        self.assertEqual(g._cache_store.mode, "enabled")

    def test_option_passee_a_llama_completion(self):
        proc = MagicMock(returncode=0, stdout="{} ", stderr="")
        with patch("premier_moteur.subprocess.run", return_value=proc) as run_mock:
            g = GenerateurLlamaCpp(
                self.chemin_modele, prompt_cache="/tmp/x.bin"
            )
            g.generer("p")
        cmd = run_mock.call_args[0][0]
        self.assertIn("--prompt-cache", cmd)
        idx = cmd.index("--prompt-cache")
        self.assertEqual(cmd[idx + 1], "/tmp/x.bin")


class TestCacheStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="beaume_cache_test_")
        self.addCleanup(self._tmpdir.cleanup)

    def _store(self, mode="enabled"):
        from cache_store import CacheStore
        s = CacheStore(mode)
        s.base = Path(self._tmpdir.name)
        return s

    def test_disabled_ne_cree_rien(self):
        s = self._store("disabled")
        self.assertIsNone(s.chemin("/m.gguf", "prefixe"))

    def _modele(self, nom):
        f = Path(self._tmpdir.name) / nom
        if not f.exists():
            f.write_bytes(b"gguf")
        return str(f)

    def test_chemin_deterministe(self):
        s = self._store()
        m = self._modele("m.gguf")
        p1 = s.chemin(m, "prefixe")
        p2 = s.chemin(m, "prefixe")
        self.assertEqual(p1, p2)

    def test_chemin_isole_par_modele_et_prefixe(self):
        s = self._store()
        p1 = s.chemin(self._modele("m1.gguf"), "prefixe")
        p2 = s.chemin(self._modele("m2.gguf"), "prefixe")
        p3 = s.chemin(self._modele("m1.gguf"), "autre")
        self.assertNotEqual(p1, p2)
        self.assertNotEqual(p1, p3)

    def test_chemin_change_quand_modele_remplace(self):
        s = self._store()
        m = self._modele("m.gguf")
        p1 = s.chemin(m, "prefixe")
        # Remplacer par un fichier de taille differente => hash different
        Path(m).write_bytes(b"gguf_v2_plus_long")
        p2 = s.chemin(m, "prefixe")
        self.assertNotEqual(p1, p2)

    def test_fichier_0600(self):
        import os
        s = self._store()
        p = s.chemin(self._modele("m.gguf"), "prefixe")
        with s.ouvert(p) as chemin:
            mode = os.stat(chemin).st_mode & 0o777
        self.assertEqual(mode, 0o600)


class TestRetryCache(_Base):
    def test_retry_sans_cache_si_code_retour_1(self):
        from premier_moteur import ResultatMoteur
        r_echec = ResultatMoteur(
            ok=False, modele=self.chemin_modele, duree_secondes=0.1,
            code_retour=1, categorie_erreur="code_non_nul",
            erreur="fingerprint mismatch",
            stderr="error: cache fingerprint mismatch",
        )
        r_ok = ResultatMoteur(
            ok=True, modele=self.chemin_modele, duree_secondes=0.1,
            code_retour=0,
            reponse_exacte='{"ok": true}', reponse='{"ok": true}',
        )
        with patch(
            "generateur_llama_cpp.executer_llama_completion",
            side_effect=[r_echec, r_ok],
        ) as mock_call:
            g = GenerateurLlamaCpp(
                self.chemin_modele,
                cache_prefixe="fixe",
                cache_mode="enabled",
            )
            tmp = tempfile.TemporaryDirectory(prefix="beaume_retry_")
            self.addCleanup(tmp.cleanup)
            g._cache_store.base = Path(tmp.name)
            g.generer("p")
            d = g.dernier_diagnostic()
        self.assertEqual(mock_call.call_count, 2)
        self.assertTrue(d.cache_retry)
        self.assertIsNone(mock_call.call_args_list[1][1].get("prompt_cache"))


class TestBypassEtLimites(_Base):
    def test_prompt_cache_explicite_leve_warning(self):
        with self.assertWarns(UserWarning):
            g = GenerateurLlamaCpp(self.chemin_modele, prompt_cache="/tmp/x.bin")
        self.assertTrue(g._cache_bypass)

    def test_prompt_cache_explicite_ne_cree_pas_de_fichier(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory(prefix="beaume_bypass_")
        self.addCleanup(tmp.cleanup)
        chemin = Path(tmp.name) / "bypass.bin"
        proc = MagicMock(returncode=0, stdout="{} ", stderr="")
        with patch("premier_moteur.subprocess.run", return_value=proc):
            with self.assertWarns(UserWarning):
                g = GenerateurLlamaCpp(
                    self.chemin_modele, prompt_cache=str(chemin)
                )
                g.generer("p")
        self.assertFalse(chemin.exists())


class TestPurgeSkipLocked(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="beaume_purge_")
        self.addCleanup(self._tmpdir.cleanup)

    def test_purge_skip_fichier_verrouille(self):
        from cache_store import CacheStore
        import cache_store as cs
        import fcntl, os
        s = CacheStore("enabled")
        s.base = Path(self._tmpdir.name)
        chemins = []
        for i in range(3):
            c = s.base / f"prompt_aaa_{i:02d}.bin"
            c.write_bytes(b"x" * 100)
            chemins.append(c)
        fd = os.open(str(chemins[0]), os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            orig_f, orig_o = cs.MAX_FICHIERS, cs.MAX_OCTETS
            cs.MAX_FICHIERS, cs.MAX_OCTETS = 0, 0
            try:
                res = s.purger()
            finally:
                cs.MAX_FICHIERS, cs.MAX_OCTETS = orig_f, orig_o
            self.assertTrue(chemins[0].exists())
            self.assertGreaterEqual(res["ignores_verrouilles"], 1)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


class TestRetryConditionne(_Base):
    def test_pas_de_retry_si_erreur_non_cache(self):
        from premier_moteur import ResultatMoteur
        r_echec = ResultatMoteur(
            ok=False, modele=self.chemin_modele, duree_secondes=0.1,
            code_retour=1, categorie_erreur="code_non_nul",
            erreur="out of memory",
            stderr="error: out of memory",
        )
        with patch(
            "generateur_llama_cpp.executer_llama_completion",
            return_value=r_echec,
        ) as mock_call:
            g = GenerateurLlamaCpp(
                self.chemin_modele,
                cache_prefixe="fixe",
                cache_mode="enabled",
            )
            tmp = tempfile.TemporaryDirectory(prefix="beaume_retry_")
            self.addCleanup(tmp.cleanup)
            g._cache_store.base = Path(tmp.name)
            g.generer("p")
        self.assertEqual(mock_call.call_count, 1)
        d = g.dernier_diagnostic()
        self.assertFalse(d.cache_retry)


if __name__ == "__main__":
    unittest.main(verbosity=2)
