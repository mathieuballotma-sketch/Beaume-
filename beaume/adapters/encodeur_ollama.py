"""Adaptateur Ollama pour l'encodage d'embeddings.

Respecte le contrat Encodeur. Utilise le modele bge-m3 en local.
Aucune donnee ne quitte la machine.
"""
import ollama

from beaume.utils.logging import get_logger

log = get_logger("encodeur_ollama")

_MODELE_PAR_DEFAUT = "bge-m3"


class EncodeurOllama:
    """Encodeur local via Ollama.

    La dimension est detectee au premier appel reel (bge-m3 = 1024).
    """

    def __init__(self, modele: str = _MODELE_PAR_DEFAUT) -> None:
        self.modele = modele
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            reponse = ollama.embeddings(model=self.modele, prompt="sonde")
            self._dimension = len(reponse["embedding"])
        return self._dimension

    def encoder(self, textes: list[str]) -> list[list[float]]:
        if not textes:
            return []
        resultats: list[list[float]] = []
        for t in textes:
            reponse = ollama.embeddings(model=self.modele, prompt=t)
            resultats.append(reponse["embedding"])
        return resultats
