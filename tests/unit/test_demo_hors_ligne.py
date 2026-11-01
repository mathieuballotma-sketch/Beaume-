from pathlib import Path
import pytest
from scripts.demo_hors_ligne import executer_demo


def test_demo_autonome(tmp_path):
    sortie = tmp_path / "rapport.md"
    executer_demo(sortie)
    texte = sortie.read_text()
    assert "aucune valeur juridique" in texte
    assert "demonstration-fixe-sans-LLM" in texte
    assert "REGLE FICTIVE" in texte


def test_demo_preserve_sortie_existante(tmp_path):
    sortie = tmp_path / "rapport.md"
    sortie.write_text("à conserver")
    with pytest.raises(FileExistsError):
        executer_demo(sortie)
    assert sortie.read_text() == "à conserver"
