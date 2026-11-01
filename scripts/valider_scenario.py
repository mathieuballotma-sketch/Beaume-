"""CLI de validation structurelle d'un scenario fictif Beaume."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Importer le paquet de l'arbre qui contient ce script, pas une
# installation editable d'un autre arbre (sinon le rapport est ecrit
# dans le mauvais depot).
RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from pydantic import ValidationError  # noqa: E402

from beaume.config.paths import DATA  # noqa: E402
from beaume.scenario import (  # noqa: E402
    CONTROLES_OBLIGATOIRES,
    CONTROLES_OBLIGATOIRES_AVEC_CALCULS,
    Scenario,
    valider_scenario,
)
from beaume.scenario.rapport import ResultatControle  # noqa: E402

RAPPORTS = DATA / "scenarios" / "rapports"


def main(chemin: Path) -> int:
    try:
        scenario = Scenario(**json.loads(chemin.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Scenario illisible ou invalide : {exc}", file=sys.stderr)
        return 3
    rapport = valider_scenario(scenario, racine=RACINE)
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    sortie = RAPPORTS / f"{scenario.scenario_id}_v{scenario.scenario_version}.json"
    if sortie.exists():
        print(f"Rapport deja present : {sortie}", file=sys.stderr)
        return 2
    sortie.write_text(
        json.dumps(rapport.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    accepte = rapport.accepte(scenario, racine=RACINE)
    print(f"Rapport ecrit : {sortie}")
    print(f"Accepte : {accepte}")
    for c in rapport.controles:
        if c.resultat is not ResultatControle.REUSSI:
            print(f"  {c.controle_id} -> {c.resultat.value} : {c.motif}")
    return 0 if accepte else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/valider_scenario.py <scenario.json>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(Path(sys.argv[1])))
