"""Tests du port Generateur et de l'adaptateur Ollama."""
import pytest

from beaume.ports.generateur import Generateur, ReponseLLM


class FauxGenerateur:
    """Generateur deterministe pour les tests. Aucun appel reseau."""

    def __init__(self, reponse: str = "ok", modele: str = "faux") -> None:
        self._reponse = reponse
        self._modele = modele
        self.appels: list[tuple[str, float]] = []

    def generer(self, prompt: str, temperature: float = 0.2) -> ReponseLLM:
        self.appels.append((prompt, temperature))
        return ReponseLLM(
            texte=self._reponse,
            modele=self._modele,
            duree_s=0.001,
            tokens_prompt=len(prompt.split()),
            tokens_reponse=len(self._reponse.split()),
        )

    def nom_modele(self) -> str:
        return self._modele


def test_faux_generateur_respecte_contrat():
    assert isinstance(FauxGenerateur(), Generateur)


def test_faux_generateur_retourne_reponse():
    g = FauxGenerateur(reponse="bonjour")
    r = g.generer("salut")
    assert r.texte == "bonjour"
    assert r.modele == "faux"
    assert r.duree_s >= 0


def test_faux_generateur_trace_appels():
    g = FauxGenerateur()
    g.generer("prompt 1")
    g.generer("prompt 2", temperature=0.5)
    assert len(g.appels) == 2
    assert g.appels[0] == ("prompt 1", 0.2)
    assert g.appels[1] == ("prompt 2", 0.5)


def test_faux_generateur_nom_modele():
    assert FauxGenerateur(modele="test-3b").nom_modele() == "test-3b"


def test_faux_generateur_deterministe():
    g1 = FauxGenerateur(reponse="x")
    g2 = FauxGenerateur(reponse="x")
    assert g1.generer("meme prompt").texte == g2.generer("meme prompt").texte


def test_generateur_ollama_transmet_num_ctx_et_schema(monkeypatch):
    from beaume.adapters import generateur_ollama

    appels = {}

    def faux_generate(**kwargs):
        appels.update(kwargs)
        return {
            "response": "{}",
            "prompt_eval_count": 12,
            "eval_count": 2,
        }

    monkeypatch.setattr(generateur_ollama.ollama, "generate", faux_generate)
    schema = {"type": "object"}
    generateur = generateur_ollama.GenerateurOllama(num_ctx=8192)

    generateur.generer("prompt", format=schema)

    assert appels["options"]["num_ctx"] == 8192
    assert appels["format"] is schema


def test_generateur_ollama_refuse_num_ctx_invalide():
    from beaume.adapters.generateur_ollama import GenerateurOllama

    with pytest.raises(ValueError, match="num_ctx"):
        GenerateurOllama(num_ctx=0)


def test_generateur_ollama_accepte_le_modele_configure_par_environnement(monkeypatch):
    from beaume.adapters.generateur_ollama import GenerateurOllama

    monkeypatch.setenv("BEAUME_MODELE_OLLAMA", "qwen2.5:7b-instruct")

    assert GenerateurOllama().nom_modele() == "qwen2.5:7b-instruct"


def _ollama_disponible() -> bool:
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _ollama_disponible(),
    reason="Ollama indisponible",
)
def test_ollama_generateur_reel():
    """Ne tourne que si Ollama est lance ET le modele pull."""
    from beaume.adapters.generateur_ollama import GenerateurOllama
    g = GenerateurOllama()
    assert isinstance(g, Generateur)
    r = g.generer("Reponds uniquement par: ok", temperature=0.0)
    assert r.texte.strip() != ""
    assert r.modele == g.nom_modele()
    assert r.duree_s > 0
