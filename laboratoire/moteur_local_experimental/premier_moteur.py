"""
premier_moteur.py — Brique de laboratoire du moteur Beaume, lot 4.

Changements par rapport au lot 3 :
- grammaire chaine élargie : Unicode (UTF-8), ponctuation, échappements JSON
  (\\" \\\\ \\/ \\b \\f \\n \\r \\t \\uXXXX). Exclut guillemets, backslash
  et octets de contrôle hors échappement. Corrige l'impossibilité de produire
  « Maître » directement.
- _detecter_template_dans_logs : motifs négatifs vérifiés en premier, motifs
  positifs spécifiques, retour None si signal ambigu. Ne retourne plus True
  sur « no chat template applied ».
- sortie_complete : True UNIQUEMENT si le marqueur est en toute fin après
  strip ET processus terminé. Nouveau champ marqueur_fin_position
  ("fin" | "milieu" | None) pour rendre visible l'observation.
- Helper chaine_est_dans_alphabet(valeur) pour les tests unitaires
  (approximation Python, pas un test du GBNF).

Aucune donnée réelle, aucun téléchargement, aucune modification des poids.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


MARQUEUR_FIN = "[end of text]"


# Règles de chaîne JSON contraintes par GBNF.
# - chaîne entre guillemets, caractères hors " \\ et octets 0x00-0x1F/0x7F
# - échappements JSON autorisés : \" \\ \/ \b \f \n \r \t et \uXXXX
# - les caractères Unicode multi-octets (UTF-8) passent car leurs octets
#   sont >= 0x80 et hors plages exclues
REGLES_CHAINE_JSON = (
    r'chaine   ::= "\"" char* "\""' + '\n'
    r'char     ::= [^"\\\x00-\x1F\x7F] | "\\" escape' + '\n'
    r'escape   ::= ["\\/bfnrt] | "u" hex hex hex hex' + '\n'
    r'hex      ::= [0-9a-fA-F]' + '\n'
)

GRAMMAIRE_JSON_SIMPLE = (
    r'root     ::= "{" ws "\"nom\"" ws ":" ws chaine ws "}"' + '\n'
    r'ws       ::= [ \t\n]{0,4}' + '\n'
    + REGLES_CHAINE_JSON
)


def chaine_est_dans_alphabet(valeur: str) -> bool:
    """Vérifie côté Python qu'une valeur n'a PAS besoin d'échappement JSON.

    True si tous les caractères sont hors guillemets, backslash et caractères
    de contrôle. Ce n'est PAS un test du GBNF (qui accepte aussi les
    échappements), c'est un test de l'alphabet direct.
    """
    for c in valeur:
        o = ord(c)
        if c in '"\\':
            return False
        if o < 0x20 or o == 0x7F:
            return False
    return True


def _decoder(brut) -> str:
    if brut is None:
        return ""
    if isinstance(brut, bytes):
        return brut.decode("utf-8", errors="replace")
    return brut


def _normaliser(brut) -> str:
    return _decoder(brut).strip()


def _preparer_fichier_temporaire(contenu: str, *, prefix: str, suffix: str) -> str:
    """Crée un fichier temporaire 0o600. Ne laisse jamais de fichier orphelin."""
    fd, chemin = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    fileobj = None
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        fileobj = os.fdopen(fd, "w", encoding="utf-8")
        fd = -1
        fileobj.write(contenu)
        fileobj.close()
        fileobj = None
        return chemin
    except Exception:
        if fileobj is not None:
            try:
                fileobj.close()
            except OSError:
                pass
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(chemin)
        except OSError:
            pass
        raise


def _detecter_template_dans_logs(stderr: str, demande: bool) -> Optional[bool]:
    """Indice basé sur les logs stderr, PAS une vérification structurelle.

    - True  : log indique explicitement qu'un template a été appliqué
    - False : log indique explicitement qu'aucun template n'a été appliqué
    - None  : pas de signal fiable (muet, ambigu, ou option non demandée)

    Ne retourne jamais True sur la simple présence du mot « template ».
    Vérification négative en premier (chevauchements : « no chat template
    applied » contient « template applied »).
    """
    if not demande or not stderr:
        return None
    sl = stderr.lower()

    negatifs = (
        "no chat template", "no template",
        "chat template not", "template not applied",
        "template disabled", "chat template disabled",
        "without chat template", "without template",
        "not using chat template",
    )
    if any(p in sl for p in negatifs):
        return False

    positifs = (
        "using chat template", "applying chat template",
        "chat template applied", "jinja template applied",
        "applied chat template", "applied jinja",
        # Sur la build b11669, -cnv avec template disponible émet
        # « chat template is available, enabling conversation mode ».
        # C'est spécifique à cette build ; à revoir si les logs changent.
        "enabling conversation mode",
        # Observés sur b11669 en mode -cnv --jinja -st, absents en -no-cnv :
        "chat template example",
        "pre-start conversation",
    )
    if any(p in sl for p in positifs):
        return True

    return None


def _retirer_marqueur_final(texte: str) -> str:
    t = texte.rstrip()
    if t.endswith(MARQUEUR_FIN):
        return t[: -len(MARQUEUR_FIN)].rstrip()
    return t


def _tenter_json(texte_exact: str) -> tuple[Optional[bool], Optional[str], Optional[str]]:
    base = (texte_exact or "").rstrip()
    try:
        json.loads(base)
        return True, None, base
    except json.JSONDecodeError as e1:
        sans = _retirer_marqueur_final(base)
        if sans != base:
            try:
                json.loads(sans)
                return True, None, sans
            except json.JSONDecodeError as e2:
                return False, str(e2), base
        return False, str(e1), base


@dataclass
class ResultatMoteur:
    ok: bool
    modele: str
    duree_secondes: float
    reponse: Optional[str] = None
    reponse_exacte: Optional[str] = None
    code_retour: Optional[int] = None
    processus_termine: bool = False
    sortie_complete: Optional[bool] = None
    marqueur_fin_present: bool = False
    marqueur_fin_position: Optional[str] = None
    prompt: Optional[str] = None
    inclure_prompt: bool = False
    prompt_dans_argv: bool = True
    template_demande: bool = False
    template_verifie: Optional[bool] = None
    schema_utilise: Optional[str] = None
    json_parse_valide: Optional[bool] = None
    json_texte_utilise: Optional[str] = None
    json_erreur: Optional[str] = None
    schema_metier_valide: Optional[bool] = None
    erreur: Optional[str] = None
    categorie_erreur: Optional[str] = None
    commande: Optional[list[str]] = None
    stderr: Optional[str] = None


def executer_llama_completion(
    chemin_modele,
    prompt,
    *,
    max_tokens: int = 256,
    temperature: float = 0.2,
    contexte: int = 2048,
    n_gpu_layers: int = 99,
    timeout: float = 300.0,
    prompt_via_fichier: bool = True,
    grammar_file: Optional[str] = None,
    grammar_json_simple: bool = False,
    chat_template: bool = False,
    inclure_prompt: bool = False,
    prompt_cache: Optional[str] = None,
) -> ResultatMoteur:
    modele = Path(chemin_modele).expanduser().resolve()
    commun = dict(
        modele=str(modele), prompt=prompt, inclure_prompt=inclure_prompt,
        prompt_dans_argv=not prompt_via_fichier, template_demande=chat_template,
    )

    def _fail(code: str, msg: str, **extra) -> ResultatMoteur:
        return ResultatMoteur(ok=False, duree_secondes=0.0, erreur=msg,
                              categorie_erreur=code, **commun, **extra)

    binaire = shutil.which("llama-completion")
    if binaire is None:
        return _fail("binaire_absent", "llama-completion introuvable dans le PATH")
    if not modele.is_file():
        return _fail("modele_introuvable", f"Fichier modèle introuvable : {modele}")

    tempfiles: list[str] = []
    try:
        commande = [binaire, "-m", str(modele)]
        commande += ["-cnv", "--jinja", "-st"] if chat_template else ["-no-cnv"]

        if prompt_via_fichier:
            try:
                chemin_prompt = _preparer_fichier_temporaire(
                    prompt, prefix="beaume_prompt_", suffix=".txt",
                )
                tempfiles.append(chemin_prompt)
            except Exception as exc:
                return _fail("preparation_prompt", f"Échec préparation du prompt : {exc}")
            commande += ["-f", chemin_prompt]
        else:
            commande += ["-p", prompt]

        commande += [
            "-n", str(max_tokens), "-c", str(contexte),
            "--temp", str(temperature), "-ngl", str(n_gpu_layers),
            "--no-display-prompt",
        ]
        if prompt_cache:
            commande += ["--prompt-cache", str(prompt_cache)]

        schema_utilise = None
        if grammar_json_simple:
            try:
                chemin_gram = _preparer_fichier_temporaire(
                    GRAMMAIRE_JSON_SIMPLE, prefix="beaume_gram_", suffix=".gbnf",
                )
                tempfiles.append(chemin_gram)
            except Exception as exc:
                return _fail("preparation_grammaire", f"Échec préparation de la grammaire : {exc}")
            commande += ["--grammar-file", chemin_gram]
            schema_utilise = 'json_simple:{"nom":string}'
        elif grammar_file:
            commande += ["--grammar-file", str(grammar_file)]
            schema_utilise = f"fichier:{grammar_file}"

        commun_full = dict(commun, schema_utilise=schema_utilise, commande=commande)

        debut = time.monotonic()
        try:
            with open("/dev/null", "rb") as stdin_vide:
                proc = subprocess.run(
                    commande, stdin=stdin_vide, capture_output=True,
                    text=True, timeout=timeout, check=False,
                )
        except subprocess.TimeoutExpired as exc:
            duree = time.monotonic() - debut
            exact = _decoder(exc.stdout)
            return ResultatMoteur(
                ok=False, duree_secondes=round(duree, 3),
                reponse=_normaliser(exc.stdout), reponse_exacte=exact,
                marqueur_fin_present=MARQUEUR_FIN in exact,
                marqueur_fin_position=(
                    "fin" if exact.rstrip().endswith(MARQUEUR_FIN) else
                    "milieu" if MARQUEUR_FIN in exact else None
                ),
                erreur=f"Timeout après {timeout} s",
                categorie_erreur="timeout", **commun_full,
            )
        except Exception as exc:
            duree = time.monotonic() - debut
            return ResultatMoteur(
                ok=False, duree_secondes=round(duree, 3),
                erreur=f"Échec du lancement : {exc}",
                categorie_erreur="lancement", **commun_full,
            )

        duree = time.monotonic() - debut
        exact = _decoder(proc.stdout)
        stderr = (proc.stderr or "").strip()
        stripped = exact.rstrip()
        marqueur_present = MARQUEUR_FIN in exact
        marqueur_en_fin = stripped.endswith(MARQUEUR_FIN)

        if marqueur_present and not marqueur_en_fin:
            marqueur_position = "milieu"
        elif marqueur_en_fin:
            marqueur_position = "fin"
        else:
            marqueur_position = None

        processus_termine = proc.returncode == 0
        # sortie_complete : True uniquement si marqueur en toute fin ET processus
        # terminé. Reste un indice : le modèle pourrait avoir écrit littéralement
        # "[end of text]" comme contenu. Documenté comme tel.
        sortie_complete = True if (processus_termine and marqueur_en_fin) else None

        template_verifie = _detecter_template_dans_logs(stderr, chat_template)

        json_ok = json_texte = json_err = None
        if schema_utilise and processus_termine:
            json_ok, json_err, json_texte = _tenter_json(exact)

        commun_full.update(
            template_verifie=template_verifie,
            json_parse_valide=json_ok,
            json_texte_utilise=json_texte,
            json_erreur=json_err,
        )

        if not processus_termine:
            return ResultatMoteur(
                ok=False, duree_secondes=round(duree, 3),
                reponse=_normaliser(exact), reponse_exacte=exact,
                processus_termine=False, sortie_complete=sortie_complete,
                marqueur_fin_present=marqueur_present,
                marqueur_fin_position=marqueur_position,
                erreur=stderr or f"llama-completion a retourné le code {proc.returncode}",
                categorie_erreur="code_non_nul", code_retour=proc.returncode,
                stderr=stderr or None,
                **commun_full,
            )

        return ResultatMoteur(
            ok=True, duree_secondes=round(duree, 3),
            reponse=_normaliser(exact), reponse_exacte=exact,
            processus_termine=True, sortie_complete=sortie_complete,
            marqueur_fin_present=marqueur_present,
            marqueur_fin_position=marqueur_position,
            code_retour=0, stderr=stderr or None, **commun_full,
        )
    finally:
        for p in tempfiles:
            try:
                os.unlink(p)
            except OSError:
                pass


def _serialiser(r: ResultatMoteur) -> dict:
    d = asdict(r)
    if not r.inclure_prompt:
        d["prompt"] = None
    return d


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Premier moteur Beaume (llama-completion)")
    parser.add_argument("--modele", required=True)
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--prompt")
    src.add_argument("--prompt-fichier", type=Path)
    parser.add_argument("--max-tokens", type=int, default=16)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--contexte", type=int, default=2048)
    parser.add_argument("--ngl", type=int, default=99)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--prompt-en-argv", action="store_true")
    parser.add_argument("--grammar-json-simple", action="store_true")
    parser.add_argument("--grammar-file", type=Path, default=None)
    parser.add_argument("--mode-chat", action="store_true")
    parser.add_argument("--inclure-prompt", action="store_true")
    args = parser.parse_args()

    if args.prompt_fichier:
        prompt = args.prompt_fichier.read_text(encoding="utf-8")
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = ("Texte fictif : Le chat de la voisine s'appelle Orion. "
                  "Réponds uniquement par le nom du chat.")

    resultat = executer_llama_completion(
        args.modele, prompt,
        max_tokens=args.max_tokens, temperature=args.temperature,
        contexte=args.contexte, n_gpu_layers=args.ngl, timeout=args.timeout,
        prompt_via_fichier=not args.prompt_en_argv,
        grammar_file=args.grammar_file,
        grammar_json_simple=args.grammar_json_simple,
        chat_template=args.mode_chat,
        inclure_prompt=args.inclure_prompt,
    )
    print(json.dumps(_serialiser(resultat), ensure_ascii=False, indent=2))
    sys.exit(0 if resultat.ok else 1)
