"""Adaptateur Ollama pour la generation de texte (LLM local).

Respecte le contrat Generateur. Utilise un modele local via Ollama.
Aucune donnee ne quitte la machine.

Mode JSON natif : Ollama supporte le constrained decoding. Le schema
JSON est defini dans beaume.application.schemas et transmis via le
parametre `format`. Cet adaptateur ne connait pas la structure du
schema : il passe ce qu'on lui donne.

Correctifs du 2026-10-18 contre les boucles de generation :

1. num_predict (plafond dur) : empeche une generation de durer 20 minutes.
   La valeur 1536 est un parametre de l'experience actuelle, pas une garantie
   de sortie complete pour tous les dossiers.

2. num_ctx : la valeur par defaut d'Ollama est 2048 tokens. Le nouveau
   prompt contient les textes des articles candidats; on demande donc
   explicitement 8192 tokens. Cela ne garantit pas que chaque prompt tienne
   dans cette fenetre : les compteurs prompt_eval_count doivent etre suivis.

3. repeat_penalty + repeat_last_n (anti-repetition) : limite certaines
   boucles observees, sans garantir qu'elles ne se reproduiront pas.
   Sans eux, le modele peut boucler jusqu'a epuisement du budget
   num_predict, produisant un JSON tronque et inutilisable.
   Les valeurs 1.15 et 256 viennent d'essais limites sur Beaume; leur effet
   sur la selection juridique doit encore etre mesure.

4. frequency_penalty + presence_penalty : desactivees par defaut. Leur effet
   sur la qualite du JSON et la selection juridique n'est pas mesure.

Ces parametres bornent ou modifient la generation; ils ne prouvent pas
que la sortie est complete, exacte ou juridiquement pertinente.
"""
from __future__ import annotations

import os
import time
from typing import Any

import ollama

from beaume.application.schemas import SCHEMA_ANALYSE
from beaume.ports.generateur import ReponseLLM
from beaume.utils.logging import get_logger

log = get_logger("generateur_ollama")

_MODELE_PAR_DEFAUT = "qwen-beaume-v1"
_ENV_MODELE = "BEAUME_MODELE_OLLAMA"

# Plafond dur de generation. Empeche une boucle de durer 20 minutes.
_NUM_PREDICT_PAR_DEFAUT = 1536
_NUM_CTX_PAR_DEFAUT = 8192

# Anti-repetition. 1.0 = desactive, > 1.0 = penalise les tokens recents.
# Valeur empirique des essais Beaume; son effet sur la qualite juridique
# doit etre compare a une baseline sur un jeu fixe.
_REPEAT_PENALTY_PAR_DEFAUT = 1.15
_REPEAT_LAST_N_PAR_DEFAUT = 256

# Penalites complementaires pour renforcer l'anti-repetition sur les
# longues sequences JSON. 0.0 = desactive.
_FREQUENCY_PENALTY_PAR_DEFAUT = 0.0
_PRESENCE_PENALTY_PAR_DEFAUT = 0.0

# Reexport pour compatibilite : certains tests importent SCHEMA_ANALYSE
# depuis ce module. La definition vit dans beaume.application.schemas.
__all__ = ["GenerateurOllama", "SCHEMA_ANALYSE"]


class GenerateurOllama:
    """Generateur de texte via Ollama, 100% local."""

    def __init__(
        self,
        modele: str | None = None,
        keep_alive: str = "24h",
        schema: dict[str, Any] | None = None,
        num_ctx: int = _NUM_CTX_PAR_DEFAUT,
        num_predict: int = _NUM_PREDICT_PAR_DEFAUT,
        repeat_penalty: float = _REPEAT_PENALTY_PAR_DEFAUT,
        repeat_last_n: int = _REPEAT_LAST_N_PAR_DEFAUT,
        frequency_penalty: float = _FREQUENCY_PENALTY_PAR_DEFAUT,
        presence_penalty: float = _PRESENCE_PENALTY_PAR_DEFAUT,
    ) -> None:
        if num_ctx <= 0:
            raise ValueError("num_ctx doit etre strictement positif")
        if num_predict <= 0:
            raise ValueError("num_predict doit etre strictement positif")
        if repeat_penalty < 1.0:
            raise ValueError("repeat_penalty doit etre >= 1.0 (1.0 = desactive)")
        if repeat_last_n < 0:
            raise ValueError("repeat_last_n doit etre >= 0")
        modele_effectif = (
            os.environ.get(_ENV_MODELE, _MODELE_PAR_DEFAUT)
            if modele is None else modele
        )
        if not modele_effectif.strip():
            raise ValueError("Le nom du modele Ollama ne peut pas etre vide")
        self.modele = modele_effectif
        self.keep_alive = keep_alive
        self.schema = schema
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.repeat_penalty = repeat_penalty
        self.repeat_last_n = repeat_last_n
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty

    def nom_modele(self) -> str:
        return self.modele

    def generer(
        self,
        prompt: str,
        temperature: float = 0.0,
        format: dict[str, Any] | str | None = None,
    ) -> ReponseLLM:
        debut = time.perf_counter()

        # Priorite : format explicite > schema instance > rien.
        format_final = format if format is not None else self.schema

        options: dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "repeat_penalty": self.repeat_penalty,
            "repeat_last_n": self.repeat_last_n,
        }
        # Les penalites de frequence/presence ne sont pas supportees
        # par toutes les versions d'Ollama ; on ne les ajoute que si
        # elles sont non nulles.
        if self.frequency_penalty > 0.0:
            options["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty > 0.0:
            options["presence_penalty"] = self.presence_penalty

        kwargs: dict[str, Any] = {
            "model": self.modele,
            "prompt": prompt,
            "options": options,
            "keep_alive": self.keep_alive,
        }
        if format_final is not None:
            kwargs["format"] = format_final

        reponse = ollama.generate(**kwargs)
        duree = time.perf_counter() - debut

        texte = reponse.get("response", "")
        tokens_prompt = reponse.get("prompt_eval_count")
        tokens_reponse = reponse.get("eval_count")

        log.info(
            "Generation %s : %d tokens prompt, %d tokens reponse, %.2f s",
            self.modele,
            tokens_prompt or 0,
            tokens_reponse or 0,
            duree,
        )
        if tokens_prompt and tokens_prompt + min(tokens_reponse or 0, self.num_predict) > self.num_ctx:
            log.warning(
                "Generation %s : prompt et sortie observes depassent num_ctx=%d; "
                "le contexte peut etre tronque ou decale.",
                self.modele,
                self.num_ctx,
            )
        if tokens_prompt and tokens_prompt > self.num_ctx - min(self.num_predict, self.num_ctx):
            log.warning(
                "Generation %s : prompt_eval_count=%d laisse peu de marge "
                "pour num_predict=%d dans num_ctx=%d.",
                self.modele,
                tokens_prompt,
                self.num_predict,
                self.num_ctx,
            )
        if tokens_reponse and tokens_reponse >= self.num_predict:
            log.warning(
                "Generation %s tronquee a num_predict=%d : le modele n'a pas "
                "produit de fin naturelle. Sortie possiblement en boucle.",
                self.modele,
                self.num_predict,
            )

        return ReponseLLM(
            texte=texte,
            modele=self.modele,
            duree_s=duree,
            tokens_prompt=tokens_prompt,
            tokens_reponse=tokens_reponse,
        )
