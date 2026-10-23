"""CLI de validation structurelle d'un scenario fictif Beaume."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from beaume.config.paths import DATA
from beaume.scenario import (
    CONTROLES_OBLIGATOIRES,
    CONTROLES_OBLIGATOIRES_AVEC_CALCULS,
    Scenario,
    valider_scenario,
)
from beaume.scenario.rapport import ResultatControle

RAPPORTS = DATA / "scenarios" / "rapports"


def main(chemin: Path) -> int:
    scenario = Scenario(**json.loads(chemin.read_text(encoding="utf-8")))
    rapport = valider_scenario(scenario)
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    sortie = RAPPORTS / f"{scenario.scenario_id}_v{scenario.scenario_version}.json"
    if sortie.exists():
        print(f"Rapport deja present : {sortie}", file=sys.stderr)
        return 2
    sortie.write_text(
        json.dumps(rapport.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    accepte = rapport.accepte(scenario)
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
