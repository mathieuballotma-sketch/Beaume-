"""Adaptateur expérimental GenerateurLlamaCpp.

Implémente le protocole Generateur de Beaume :
    nom_modele() -> str
    generer(prompt, temperature=0.2, format=None) -> ReponseLLM

ReponseLLM est recopiée localement, IDENTIQUE au port de production
(beaume/ports/generateur.py). Aucun import de production.

Stratégie de génération structurée :
- si format fourni et dans le sous-ensemble convertible : grammaire GBNF
  pour la forme, validation post-génération pour uniqueItems, bornes,
  additionalProperties ;
- si format hors sous-ensemble : SchemaNonSupporte levée explicitement.

Sépare :
- processus exécuté / en échec ;
- JSON parsable ;
- conformité technique au schéma (validateur_beaume) ;
- schema_metier_valide : TOUJOURS None (hors moteur).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from premier_moteur import (
    _preparer_fichier_temporaire,
    _retirer_marqueur_final,
    executer_llama_completion,
)
from schema_beaume import SchemaNonSupporte, generer_gbnf
from validateur_beaume import ResultatValidation, valider
from cache_store import CacheStore


@dataclass(frozen=True)
class ReponseLLM:
    """Identique à beaume.ports.generateur.ReponseLLM (production)."""
    texte: str
    modele: str
    duree_s: float
    tokens_prompt: int | None = None
    tokens_reponse: int | None = None


@dataclass
class DiagnosticMoteur:
    """État du dernier appel, même si ReponseLLM.texte est vide.

    cause="preparation_grammaire" : la grammaire n'a pas pu être créée
    cause="processus" : llama-completion a échoué
    cause="json_invalide" : sortie non parsable
    cause="schema_invalide" : JSON parsable mais schéma non respecté
    cause=None, ok=True : succès
    """
    ok: bool
    cause: Optional[str] = None
    processus_termine: bool = False
    categorie_erreur_moteur: Optional[str] = None
    erreur_moteur: Optional[str] = None
    json_parse_valide: Optional[bool] = None
    schema_technique_valide: Optional[bool] = None
    violations: list = field(default_factory=list)
    cache_utilise: bool = False
    cache_retry: bool = False


_RE_PROMPT_TOKENS = re.compile(
    r"prompt eval time\s*=\s*[0-9.]+\s*ms\s*/\s*(\d+)\s*tokens"
)
_RE_EVAL_TOKENS = re.compile(
    r"eval time\s*=\s*[0-9.]+\s*ms\s*/\s*(\d+)\s*runs?"
)


def _extraire_tokens(stderr: str) -> tuple[Optional[int], Optional[int]]:
    """Extrait (tokens_prompt, tokens_reponse) depuis stderr.

    Défensif : retourne (None, None) si les motifs ne sont pas trouvés.
    Les valeurs sont issues du format de log de llama.cpp b11669 ; un
    changement de version peut les faire disparaître.
    """
    tp = _RE_PROMPT_TOKENS.search(stderr or "")
    tr = _RE_EVAL_TOKENS.search(stderr or "")
    return (
        int(tp.group(1)) if tp else None,
        int(tr.group(1)) if tr else None,
    )


def _extraire_json(texte: str) -> str:
    """Retire le marqueur de fin éventuel, retourne le JSON brut.

    Ne lève pas : le validateur signalera un JSON invalide.
    """
    return _retirer_marqueur_final(texte or "").strip()


class GenerateurLlamaCpp:
    """Adaptateur expérimental, contrat Generateur identique à Ollama.

    Ne gère pas le cycle de vie du modèle : chaque appel recharge le GGUF.
    Coût mesuré au lot 3 : ~3 s de chargement par appel.
    """

    def __init__(
        self,
        chemin_modele: str,
        *,
        max_tokens: int = 1024,
        contexte: int = 4096,
        n_gpu_layers: int = 99,
        timeout: float = 300.0,
        prompt_cache: Optional[str] = None,
        cache_prefixe: Optional[str] = None,
        cache_mode: str = "disabled",
    ):
        self._chemin_modele = str(
            Path(chemin_modele).expanduser().resolve()
        )
        self._max_tokens = max_tokens
        self._contexte = contexte
        self._n_gpu_layers = n_gpu_layers
        self._timeout = timeout
        self._cache_bypass = prompt_cache is not None
        if self._cache_bypass:
            import warnings
            warnings.warn(
                "prompt_cache= contourne CacheStore (permissions 0600, "
                "flock, purge non appliques). Usage laboratoire.",
                stacklevel=2,
            )
        self._prompt_cache = str(prompt_cache) if prompt_cache else None
        self._cache_prefixe = cache_prefixe
        self._cache_store = (
            CacheStore(cache_mode)
            if (cache_prefixe and cache_mode != "disabled") else None
        )
        self._derniere_validation: Optional[ResultatValidation] = None
        self._dernier_diagnostic: Optional[DiagnosticMoteur] = None

    def nom_modele(self) -> str:
        """Identifiant stable : le chemin résolu du GGUF."""
        return self._chemin_modele

    def derniere_validation(self) -> Optional[ResultatValidation]:
        """Résultat de validation du dernier appel, None si aucun format."""
        return self._derniere_validation

    def dernier_diagnostic(self) -> Optional[DiagnosticMoteur]:
        """Diagnostic du dernier appel, distinct de derniere_validation()."""
        return self._dernier_diagnostic

    def generer(
        self,
        prompt: str,
        temperature: float = 0.2,
        format: dict[str, Any] | str | None = None,
    ) -> ReponseLLM:
        self._derniere_validation = None
        self._dernier_diagnostic = None

        def _diag(cause, *, proc_ok=False, cat=None, err=None,
                  jp=None, stv=None, viol=None,
                  cache_utilise=False, cache_retry=False):
            self._dernier_diagnostic = DiagnosticMoteur(
                ok=(cause is None),
                cause=cause,
                processus_termine=proc_ok,
                categorie_erreur_moteur=cat,
                erreur_moteur=err,
                json_parse_valide=jp,
                schema_technique_valide=stv,
                violations=list(viol or []),
                cache_utilise=cache_utilise,
                cache_retry=cache_retry,
            )

        if isinstance(format, str):
            _diag("preparation_grammaire", err="format str non supporté")
            raise SchemaNonSupporte(
                "format de type str non supporté : fournir un dict"
            )

        gramm_path = None
        cache_utilise = False
        cache_retry = False
        try:
            if format is not None:
                try:
                    gbnf = generer_gbnf(format)
                except SchemaNonSupporte:
                    _diag("preparation_grammaire",
                          err="schéma hors sous-ensemble")
                    raise
                try:
                    gramm_path = _preparer_fichier_temporaire(
                        gbnf, prefix="beaume_schema_", suffix=".gbnf"
                    )
                except Exception as exc:
                    _diag("preparation_grammaire", err=str(exc))
                    return ReponseLLM(
                        texte="", modele=self._chemin_modele, duree_s=0.0
                    )

            kwargs = dict(
                max_tokens=self._max_tokens,
                temperature=temperature,
                contexte=self._contexte,
                n_gpu_layers=self._n_gpu_layers,
                timeout=self._timeout,
                grammar_file=gramm_path,
                inclure_prompt=False,
            )
            if self._cache_store is not None:
                chemin = self._cache_store.chemin(
                    self._chemin_modele, self._cache_prefixe
                )
                with self._cache_store.ouvert(chemin) as pc:
                    r = executer_llama_completion(
                        self._chemin_modele, prompt,
                        prompt_cache=str(pc), **kwargs
                    )
                cache_utilise = True
            else:
                r = executer_llama_completion(
                    self._chemin_modele, prompt,
                    prompt_cache=self._prompt_cache, **kwargs
                )
            if r.code_retour == 1 and cache_utilise:
                err_l = (r.stderr or "").lower()
                indices_cache = (
                    "fingerprint", "cache", "incompatib",
                )
                if any(k in err_l for k in indices_cache):
                    cache_retry = True
                    r = executer_llama_completion(
                        self._chemin_modele, prompt,
                        prompt_cache=None, **kwargs
                    )
        finally:
            if gramm_path is not None:
                try:
                    os.unlink(gramm_path)
                except OSError:
                    pass

        tp, tr = _extraire_tokens(r.stderr or "")
        texte = r.reponse_exacte or r.reponse or ""

        if not r.ok:
            _diag("processus", proc_ok=False, cat=r.categorie_erreur,
                  err=r.erreur, cache_utilise=cache_utilise,
                  cache_retry=cache_retry)
            return ReponseLLM(
                texte="", modele=self._chemin_modele,
                duree_s=r.duree_secondes,
                tokens_prompt=tp, tokens_reponse=tr,
            )

        if format is not None:
            texte_a_valider = _extraire_json(texte)
            v = valider(texte_a_valider, format)
            self._derniere_validation = v
            if not v.json_parse_valide:
                _diag("json_invalide", proc_ok=True, jp=False,
                      stv=False, err=v.erreur_parse,
                      cache_utilise=cache_utilise,
                      cache_retry=cache_retry)
                texte = ""
            elif not v.schema_technique_valide:
                _diag("schema_invalide", proc_ok=True, jp=True,
                      stv=False, viol=v.violations,
                      cache_utilise=cache_utilise,
                      cache_retry=cache_retry)
                texte = ""
            else:
                _diag(None, proc_ok=True, jp=True, stv=True,
                      cache_utilise=cache_utilise,
                      cache_retry=cache_retry)
        else:
            _diag(None, proc_ok=True,
                  cache_utilise=cache_utilise,
                  cache_retry=cache_retry)

        return ReponseLLM(
            texte=texte, modele=self._chemin_modele,
            duree_s=r.duree_secondes,
            tokens_prompt=tp, tokens_reponse=tr,
        )

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Adaptateur GenerateurLlamaCpp expérimental"
    )
    parser.add_argument("--modele", required=True)
    parser.add_argument(
        "--prompt",
        default=(
            "Dossier fictif. Article A1, fichier d.pdf, pages 1 et 2. "
            "Retourne l'analyse JSON avec contexte et citations."
        ),
    )
    parser.add_argument("--schema-fichier", required=True)
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--temperature", type=float, default=0.0)
    args = parser.parse_args()

    schema = json.loads(
        Path(args.schema_fichier).read_text(encoding="utf-8")
    )
    g = GenerateurLlamaCpp(
        args.modele, max_tokens=args.max_tokens
    )
    print("nom_modele:", g.nom_modele())
    r = g.generer(
        args.prompt,
        temperature=args.temperature,
        format=schema,
    )
    print("=== ReponseLLM ===")
    print("modele:", r.modele)
    print("duree_s: %.3f" % r.duree_s)
    print("tokens_prompt:", r.tokens_prompt)
    print("tokens_reponse:", r.tokens_reponse)
    print("texte (200 premiers):", r.texte[:200])
    v = g.derniere_validation()
    print("=== Validation ===")
    print("json_parse_valide:", v.json_parse_valide)
    print("schema_technique_valide:", v.schema_technique_valide)
    print("schema_metier_valide:", v.schema_metier_valide)
    if v.violations:
        print("violations:")
        for x in v.violations:
            print(" -", x)
