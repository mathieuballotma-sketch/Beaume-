"""Split train/test du dataset d'entrainement, par fait (pas par ligne).

Entree  : data/training/dataset_entrainement.parquet
Sorties : data/training/dataset_train.parquet
          data/training/dataset_test.parquet
          data/training/test_ids.json
"""
from __future__ import annotations

import json

import pandas as pd

from beaume.config import paths

CHEMIN_ENTREE = paths.DATA / "training" / "dataset_entrainement.parquet"
CHEMIN_TRAIN = paths.DATA / "training" / "dataset_train.parquet"
CHEMIN_TEST = paths.DATA / "training" / "dataset_test.parquet"
CHEMIN_TEST_IDS = paths.DATA / "training" / "test_ids.json"

N_TEST = 15
RANDOM_STATE = 42


def main() -> int:
    if not CHEMIN_ENTREE.exists():
        raise SystemExit(f"Introuvable : {CHEMIN_ENTREE}")

    df = pd.read_parquet(CHEMIN_ENTREE)

    if "id_fait" not in df.columns:
        raise SystemExit(
            "Colonne 'id_fait' absente. Relance construire_dataset_entrainement.py"
        )

    ids_uniques = df["id_fait"].dropna().unique().tolist()
    if len(ids_uniques) <= N_TEST:
        raise SystemExit(
            f"Pas assez de faits ({len(ids_uniques)}) pour un test de {N_TEST}."
        )

    rng = pd.Series(ids_uniques).sample(n=N_TEST, random_state=RANDOM_STATE)
    ids_test = set(rng.tolist())
    ids_train = set(ids_uniques) - ids_test

    df_train = df[df["id_fait"].isin(ids_train)].reset_index(drop=True)
    df_test = df[df["id_fait"].isin(ids_test)].reset_index(drop=True)

    df_train.to_parquet(CHEMIN_TRAIN, index=False)
    df_test.to_parquet(CHEMIN_TEST, index=False)

    CHEMIN_TEST_IDS.parent.mkdir(parents=True, exist_ok=True)
    CHEMIN_TEST_IDS.write_text(
        json.dumps(sorted(ids_test), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== Split ===")
    print(f"Faits total         : {len(ids_uniques)}")
    print(f"Faits train         : {len(ids_train)}")
    print(f"Faits test          : {len(ids_test)}")
    print(f"Paires train        : {len(df_train)}")
    print(f"Paires test         : {len(df_test)}")
    print(f"IDs test            : {CHEMIN_TEST_IDS}")
    print()
    print("ATTENTION : ces IDs ne doivent JAMAIS reapparaitre dans le train.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())