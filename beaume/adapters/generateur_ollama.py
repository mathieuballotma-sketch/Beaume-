"""Adaptateur Ollama pour la generation de texte (LLM local).

Respecte le contrat Generateur. Utilise un modele local via Ollama.
Aucune donnee ne quitte la machine.

Mode JSON natif : Ollama supporte le constrained decoding. Le schema
JSON est defini dans beaume.application.schemas et transmis via le
parametre `format`. Cet adaptateur ne connait pas la structure du
schema : il passe ce qu'on lui donne.
"""
from __future__ import annotations

import time
from typing import Any

import ollama

from beaume.application.schemas import SCHEMA_ANALYSE
from beaume.ports.generateur import ReponseLLM
from beaume.utils.logging import get_logger

log = get_logger("generateur_ollama")

_MODELE_PAR_DEFAUT = "qwen2.5:7b-instruct"

# Reexport pour compatibilite : certains tests importent SCHEMA_ANALYSE
# depuis ce module. La definition vit dans beaume.application.schemas.
__all__ = ["GenerateurOllama", "SCHEMA_ANALYSE"]


class GenerateurOllama:
    """Generateur de texte via Ollama, 100% local."""

    def __init__(
        self,
        modele: str = _MODELE_PAR_DEFAUT,
        keep_alive: str = "24h",
        schema: dict[str, Any] | None = None,
    ) -> None:
        self.modele = modele
        self.keep_alive = keep_alive
        self.schema = schema

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

        kwargs: dict[str, Any] = {
            "model": self.modele,
            "prompt": prompt,
            "options": {"temperature": temperature},
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

        return ReponseLLM(
            texte=texte,
            modele=self.modele,
            duree_s=duree,
            tokens_prompt=tokens_prompt,
            tokens_reponse=tokens_reponse,
        )