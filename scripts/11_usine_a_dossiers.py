"""Entrée de compatibilité de l'usine historique désactivée.

Le module et ses limites sont décrits dans scripts/experimental/README.md.
"""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "experimental" / "usine_historique.py"),
        run_name="__main__",
    )
