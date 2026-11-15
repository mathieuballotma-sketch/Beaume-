"""Tests unitaires lot 4 — aucun modèle chargé."""
import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import premier_moteur as pm
from premier_moteur import (
    GRAMMAIRE_JSON_SIMPLE,
    MARQUEUR_FIN,
    _decoder,
    _detecter_template_dans_logs,
    _normaliser,
    _preparer_fichier_temporaire,
    _retirer_marqueur_final,
    _tenter_json,
    chaine_est_dans_alphabet,
    executer_llama_completion,
)


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


class TestDecoderNormaliser(unittest.TestCase):
    def test_decoder_preserve_espaces(self):
        self.assertEqual(
            _decoder(b" Orion. " + MARQUEUR_FIN.encode() + b"\n\n"),
            " Orion. " + MARQUEUR_FIN + "\n\n",
        )
    def test_decoder_none(self):
        self.assertEqual(_decoder(None), "")
    def test_normaliser_strip(self):
        self.assertEqual(
            _normaliser(" x " + MARQUEUR_FIN + "\n\n"),
            "x " + MARQUEUR_FIN,
        )
    def test_normaliser_bytes(self):
        self.assertEqual(
            _normaliser(b" x " + MARQUEUR_FIN.encode()),
            "x " + MARQUEUR_FIN,
        )
    def test_normaliser_none(self):
        self.assertEqual(_normaliser(None), "")


class TestMarqueur(unittest.TestCase):
    def test_retire_en_fin(self):
        self.assertEqual(_retirer_marqueur_final("x " + MARQUEUR_FIN), "x")
    def test_ne_retire_pas_au_milieu(self):
        s = "voici " + MARQUEUR_FIN + " puis suite"
        self.assertEqual(_retirer_marqueur_final(s), s)
    def test_absent(self):
        self.assertEqual(_retirer_marqueur_final("x"), "x")


class TestTenterJson(unittest.TestCase):
    def test_json_propre(self):
        ok, err, txt = _tenter_json('{"nom": "Orion"}')
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(txt, '{"nom": "Orion"}')
    def test_json_avec_marqueur(self):
        ok, err, txt = _tenter_json('{"nom": "Orion"} ' + MARQUEUR_FIN)
        self.assertTrue(ok)
        self.assertEqual(txt, '{"nom": "Orion"}')
    def test_json_invalide(self):
        ok, err, _ = _tenter_json("{pas du json}")
        self.assertFalse(ok)
        self.assertTrue(err)


class TestPreparerFichier(unittest.TestCase):
    def test_succes(self):
        chemin = _preparer_fichier_temporaire(
            "contenu", prefix="t_", suffix=".txt"
        )
        self.addCleanup(
            lambda: os.path.exists(chemin) and os.unlink(chemin)
        )
        with open(chemin, encoding="utf-8") as f:
            self.assertEqual(f.read(), "contenu")

    def test_echec_fdopen(self):
        captures = {}
        real = tempfile.mkstemp
        def cap(prefix, suffix):
            c = real(prefix=prefix, suffix=suffix)
            captures["c"] = c[1]
            return c
        with patch("premier_moteur.tempfile.mkstemp", side_effect=cap):
            with patch("premier_moteur.os.fdopen",
                       side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    _preparer_fichier_temporaire(
                        "x", prefix="t_", suffix=".txt"
                    )
        self.assertFalse(os.path.exists(captures["c"]))

    def test_echec_write(self):
        captures = {}
        real = tempfile.mkstemp
        def cap(prefix, suffix):
            c = real(prefix=prefix, suffix=suffix)
            captures["c"] = c[1]
            return c
        faux = MagicMock()
        faux.write.side_effect = OSError("disk")
        with patch("premier_moteur.tempfile.mkstemp", side_effect=cap):
            with patch("premier_moteur.os.fdopen", return_value=faux):
                with self.assertRaises(OSError):
                    _preparer_fichier_temporaire(
                        "x", prefix="t_", suffix=".txt"
                    )
        self.assertFalse(os.path.exists(captures["c"]))
        faux.close.assert_called()


class TestTemplateDetection(unittest.TestCase):
    def test_non_demande(self):
        self.assertIsNone(
            _detecter_template_dans_logs("chat template", False)
        )
    def test_logs_muets(self):
        self.assertIsNone(_detecter_template_dans_logs("", True))
    def test_log_ambigu(self):
        self.assertIsNone(
            _detecter_template_dans_logs("chat template", True)
        )
    def test_no_chat_template_applied(self):
        self.assertFalse(
            _detecter_template_dans_logs("no chat template applied", True)
        )
    def test_using_chat_template(self):
        self.assertTrue(
            _detecter_template_dans_logs("using chat template", True)
        )
    def test_chat_template_applied(self):
        self.assertTrue(
            _detecter_template_dans_logs("chat template applied", True)
        )
    def test_enabling_conversation_mode(self):
        self.assertTrue(
            _detecter_template_dans_logs("enabling conversation mode", True)
        )
    def test_template_disabled(self):
        self.assertFalse(
            _detecter_template_dans_logs("template disabled", True)
        )


class TestAlphabetChaine(unittest.TestCase):
    def test_francais(self):
        self.assertTrue(chaine_est_dans_alphabet("Maître Dupont"))
    def test_unicode(self):
        self.assertTrue(chaine_est_dans_alphabet("Ça — c'est ça"))
    def test_ponctuation(self):
        self.assertTrue(
            chaine_est_dans_alphabet("Dupont & Associes, 2024-0042.")
        )
    def test_vide(self):
        self.assertTrue(chaine_est_dans_alphabet(""))
    def test_guillemet_refuse(self):
        self.assertFalse(chaine_est_dans_alphabet('a"b'))
    def test_backslash_refuse(self):
        self.assertFalse(chaine_est_dans_alphabet('a\\b'))
    def test_control_refuse(self):
        self.assertFalse(chaine_est_dans_alphabet('a\nb'))
        self.assertFalse(chaine_est_dans_alphabet('a\tb'))


class TestGrammaireGBNF(unittest.TestCase):
    def test_contient_escape(self):
        self.assertIn("escape", GRAMMAIRE_JSON_SIMPLE)
    def test_contient_hex(self):
        self.assertIn("hex", GRAMMAIRE_JSON_SIMPLE)
    def test_contient_u_unicode(self):
        self.assertIn('"u"', GRAMMAIRE_JSON_SIMPLE)
    def test_plus_alphabet_restrictif(self):
        self.assertNotIn("[a-zA-Z0-9 ._-]", GRAMMAIRE_JSON_SIMPLE)


class TestTimeout(_Base):
    def test_timeout_bytes_conserve_exact(self):
        exc = subprocess.TimeoutExpired(
            cmd=["x"], timeout=1.0, output=b"Orion partiel"
        )
        with patch("premier_moteur.subprocess.run", side_effect=exc):
            r = executer_llama_completion(
                self.chemin_modele, "fictif", timeout=1.0
            )
        self.assertFalse(r.ok)
        self.assertEqual(r.categorie_erreur, "timeout")
        self.assertEqual(r.reponse_exacte, "Orion partiel")
        self.assertFalse(r.processus_termine)

    def test_timeout_none(self):
        exc = subprocess.TimeoutExpired(
            cmd=["x"], timeout=1.0, output=None
        )
        with patch("premier_moteur.subprocess.run", side_effect=exc):
            r = executer_llama_completion(
                self.chemin_modele, "fictif", timeout=1.0
            )
        self.assertEqual(r.reponse_exacte, "")


class TestSucces(_Base):
    def test_prompt_masque(self):
        proc = MagicMock(returncode=0, stdout="Orion.\n", stderr="")
        with patch("premier_moteur.subprocess.run", return_value=proc):
            r = executer_llama_completion(self.chemin_modele, "PROMPT")
        self.assertFalse(r.inclure_prompt)
        self.assertIsNone(pm._serialiser(r)["prompt"])

    def test_prompt_inclus(self):
        proc = MagicMock(returncode=0, stdout="Orion.\n", stderr="")
        with patch("premier_moteur.subprocess.run", return_value=proc):
            r = executer_llama_completion(
                self.chemin_modele, "PROMPT", inclure_prompt=True
            )
        self.assertEqual(pm._serialiser(r)["prompt"], "PROMPT")

    def test_reponse_exacte(self):
        proc = MagicMock(
            returncode=0, stdout="  Orion. \n\n", stderr=""
        )
        with patch("premier_moteur.subprocess.run", return_value=proc):
            r = executer_llama_completion(self.chemin_modele, "x")
        self.assertEqual(r.reponse_exacte, "  Orion. \n\n")
        self.assertEqual(r.reponse, "Orion.")

    def test_template_demande_non_verifie(self):
        proc = MagicMock(returncode=0, stdout="Orion\n", stderr="")
        with patch("premier_moteur.subprocess.run", return_value=proc):
            r = executer_llama_completion(
                self.chemin_modele, "x", chat_template=True
            )
        self.assertTrue(r.template_demande)
        self.assertIsNone(r.template_verifie)

    def test_template_verifie(self):
        proc = MagicMock(
            returncode=0, stdout="Orion\n",
            stderr="using chat template jinja"
        )
        with patch("premier_moteur.subprocess.run", return_value=proc):
            r = executer_llama_completion(
                self.chemin_modele, "x", chat_template=True
            )
        self.assertTrue(r.template_verifie)

    def test_template_faux_positif_evite(self):
        proc = MagicMock(
            returncode=0, stdout="Orion\n",
            stderr="no chat template applied"
        )
        with patch("premier_moteur.subprocess.run", return_value=proc):
            r = executer_llama_completion(
                self.chemin_modele, "x", chat_template=True
            )
        self.assertFalse(r.template_verifie)

    def test_grammaire_json_valide(self):
        proc = MagicMock(
            returncode=0,
            stdout='{"nom": "Orion"} ' + MARQUEUR_FIN,
            stderr="",
        )
        with patch("premier_moteur.subprocess.run", return_value=proc):
            r = executer_llama_completion(
                self.chemin_modele, "x", grammar_json_simple=True
            )
        self.assertTrue(r.ok)
        self.assertTrue(r.json_parse_valide)
        self.assertEqual(r.json_texte_utilise, '{"nom": "Orion"}')
        self.assertIsNone(r.schema_metier_valide)


class TestSortieComplete(_Base):
    def _run(self, stdout, returncode=0):
        proc = MagicMock(
            returncode=returncode, stdout=stdout, stderr=""
        )
        with patch("premier_moteur.subprocess.run", return_value=proc):
            return executer_llama_completion(self.chemin_modele, "x")

    def test_fin_et_processus_ok(self):
        r = self._run("Orion " + MARQUEUR_FIN)
        self.assertTrue(r.sortie_complete)
        self.assertEqual(r.marqueur_fin_position, "fin")

    def test_fin_mais_processus_ko(self):
        r = self._run("Orion " + MARQUEUR_FIN, returncode=1)
        self.assertFalse(r.ok)
        self.assertIsNone(r.sortie_complete)
        self.assertEqual(r.marqueur_fin_position, "fin")

    def test_marqueur_au_milieu(self):
        r = self._run("a " + MARQUEUR_FIN + " b")
        self.assertIsNone(r.sortie_complete)
        self.assertEqual(r.marqueur_fin_position, "milieu")

    def test_pas_de_marqueur(self):
        r = self._run("Orion")
        self.assertIsNone(r.sortie_complete)
        self.assertIsNone(r.marqueur_fin_position)

    def test_marqueur_fin_mais_texte_apres(self):
        r = self._run("Orion " + MARQUEUR_FIN + " extra")
        self.assertIsNone(r.sortie_complete)
        self.assertEqual(r.marqueur_fin_position, "milieu")


class TestEchec(_Base):
    def test_code_non_nul(self):
        proc = MagicMock(returncode=1, stdout="", stderr="erreur")
        with patch("premier_moteur.subprocess.run", return_value=proc):
            r = executer_llama_completion(self.chemin_modele, "x")
        self.assertFalse(r.ok)
        self.assertEqual(r.categorie_erreur, "code_non_nul")

    def test_echec_preparation_prompt(self):
        with patch(
            "premier_moteur._preparer_fichier_temporaire",
            side_effect=OSError("plein"),
        ):
            r = executer_llama_completion(self.chemin_modele, "x")
        self.assertFalse(r.ok)
        self.assertEqual(r.categorie_erreur, "preparation_prompt")
        self.assertIsNone(r.commande)


class TestModeleIntrouvable(unittest.TestCase):
    def test(self):
        chemin = f"/tmp/inexistant_{os.getpid()}.gguf"
        r = executer_llama_completion(chemin, "x")
        self.assertFalse(r.ok)
        self.assertEqual(r.categorie_erreur, "modele_introuvable")


class TestTemplateDetectionB11669(unittest.TestCase):
    """Motifs observés sur b11669 avec -cnv --jinja, absents avec -no-cnv.
    Non-régression : si les logs de llama-completion changent, ces tests
    signaleront que les motifs ne sont plus discriminants."""

    def test_chat_template_example(self):
        self.assertTrue(_detecter_template_dans_logs(
            "I llama_completion: chat template example:", True))

    def test_pre_start_conversation(self):
        self.assertTrue(_detecter_template_dans_logs(
            "W *** User-specified prompt will pre-start conversation, "
            "did you mean to set --system-prompt", True))

    def test_absent_en_mode_no_cnv(self):
        self.assertIsNone(_detecter_template_dans_logs(
            "I llama_completion: llama backend init", True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
