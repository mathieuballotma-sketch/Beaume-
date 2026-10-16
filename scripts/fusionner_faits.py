"""Fusionne deux fichiers faits_clients en dedoublonnant par id."""
from __future__ import annotations

import json
from pathlib import Path

CHEMIN_A = Path("data/training/faits_clients_2.jsonl")
CHEMIN_B = Path("data/training/faits_clients_3.jsonl")
CHEMIN_SORTIE = Path("data/training/faits_clients_final.jsonl")


def main() -> int:
    vus: set[str] = set()
    n_total = 0
    n_uniques = 0

    with CHEMIN_SORTIE.open("w", encoding="utf-8") as f_out:
        for chemin in (CHEMIN_A, CHEMIN_B):
            if not chemin.exists():
                print(f"Introuvable : {chemin}")
                continue
            with chemin.open(encoding="utf-8") as f_in:
                for ligne in f_in:
                    n_total += 1
                    try:
                        d = json.loads(ligne)
                    except json.JSONDecodeError:
                        continue
                    if d.get("id") in vus:
                        continue
                    vus.add(d["id"])
                    f_out.write(json.dumps(d, ensure_ascii=False) + "\n")
                    n_uniques += 1

    print(f"Lignes lues    : {n_total}")
    print(f"Paires uniques : {n_uniques}")
    print(f"Doublons       : {n_total - n_uniques}")
    print(f"Sortie         : {CHEMIN_SORTIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())