"""Point d'entree reserve a l'integration d'AgentPublic/legi.

Cette integration n'est pas implementee : la source locale et la regle qui
associe les documents LEGI aux codes juridiques n'ont pas ete validees.
Ce point d’entree est distinct de la reconstruction du stock DILA.
Son nom historique ne permet pas de deduire l’origine ni la validite d’une
base locale appelee legi_full_v2.sqlite.
"""
from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.error(
        "integration AgentPublic/legi non implementee dans ce script. "
        "Pour le stock DILA, consulter docs/CORPUS_DILA.md et "
        "scripts/reconstruire_corpus_dila.py. Le nom d’une base v2 ne "
        "prouve ni sa provenance ni sa validation."
    )
    return 2  # pragma: no cover - argparse.error leve SystemExit


if __name__ == "__main__":
    raise SystemExit(main())
