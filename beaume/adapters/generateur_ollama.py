"""Adaptateur Ollama pour la generation de texte (LLM local).

Respecte le contrat Generateur. Utilise un modele local via Ollama.
Aucune donnee ne quitte la machine.
"""
import time

import ollama

from beaume.ports.generateur import ReponseLLM
from beaume.utils.logging import get_logger

log = get_logger("generateur_ollama")

_MODELE_PAR_DEFAUT = "qwen2.5:7b-instruct"


class GenerateurOllama:
    """Generateur de texte via Ollama, 100% local."""

    def __init__(
        self,
        modele: str = _MODELE_PAR_DEFAUT,
        keep_alive: str = "24h",
    ) -> None:
        self.modele = modele
        self.keep_alive = keep_alive

    def nom_modele(self) -> str:
        return self.modele

    def generer(
        self,
        prompt: str,
        temperature: float = 0.2,
    ) -> ReponseLLM:
        debut = time.perf_counter()
        reponse = ollama.generate(
            model=self.modele,
            prompt=prompt,
            options={"temperature": temperature},
            keep_alive=self.keep_alive,
        )
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
