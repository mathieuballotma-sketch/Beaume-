"""Tests du port Encodeur et de l'adaptateur Ollama.

Le test d'integration se saute automatiquement si Ollama n'est pas
disponible.
"""
import pytest

from beaume.ports.encodeur import Encodeur


class FauxEncodeur:
    def __init__(self, dimension: int = 4) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def encoder(self, textes: list[str]) -> list[list[float]]:
        resultats = []
        for t in textes:
            h = hash(t) % 1000
            resultats.append(
                [float((h + i) % 100) for i in range(self._dimension)]
            )
        return resultats


def test_faux_encodeur_respecte_contrat():
    assert isinstance(FauxEncodeur(), Encodeur)


def test_faux_encodeur_dimension():
    e = FauxEncodeur(dimension=8)
    assert e.dimension == 8


def test_faux_encodeur_retourne_bon_nombre_de_vecteurs():
    e = FauxEncodeur(dimension=4)
    vecteurs = e.encoder(["un", "deux", "trois"])
    assert len(vecteurs) == 3
    for v in vecteurs:
        assert len(v) == 4


def test_faux_encodeur_deterministe():
    e = FauxEncodeur()
    a = e.encoder(["contrat de travail"])
    b = e.encoder(["contrat de travail"])
    assert a == b


def test_encodeur_liste_vide():
    e = FauxEncodeur()
    assert e.encoder([]) == []


def _ollama_disponible() -> bool:
    try:
        import ollama
        ollama.embeddings(model="bge-m3", prompt="ping")
        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _ollama_disponible(),
    reason="Ollama ou bge-m3 indisponible",
)
def test_ollama_encodeur_reel():
    from beaume.adapters.encodeur_ollama import EncodeurOllama
    e = EncodeurOllama()
    assert isinstance(e, Encodeur)
    vecteurs = e.encoder(["contrat de travail", "bail commercial"])
    assert len(vecteurs) == 2
    assert len(vecteurs[0]) == e.dimension
    assert e.dimension > 0
