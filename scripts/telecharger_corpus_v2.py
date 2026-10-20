"""Point d'entree reserve a l'integration d'AgentPublic/legi.

Cette integration n'est pas implementee : la source locale et la regle qui
associe les documents LEGI aux codes juridiques n'ont pas ete validees.
Utiliser ce script comme si la base v2 existait produirait une fausse
impression de succes.
"""
from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.error(
        "integration AgentPublic/legi non implementee : aucun corpus v2 "
        "n'a ete construit ni valide. Le fichier data/vector/legi_full_v2.sqlite "
        "actuel ne doit pas etre utilise comme corpus."
    )
    return 2  # pragma: no cover - argparse.error leve SystemExit


if __name__ == "__main__":
    raise SystemExit(main())
