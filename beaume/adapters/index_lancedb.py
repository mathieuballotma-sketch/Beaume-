"""Adaptateur LanceDB : stockage vectoriel embarque, local.

Respecte le contrat IndexVectoriel. Un dossier = une base.
Aucune donnee ne quitte la machine.
"""
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

from beaume.ports.index_vectoriel import (
    ElementIndexe,
    ResultatRecherche,
)


class IndexLanceDB:
    """Index vectoriel base sur LanceDB, persistant sur disque."""

    def __init__(self, chemin: Path, nom_table: str, dimension: int) -> None:
        self.chemin = Path(chemin)
        self.chemin.mkdir(parents=True, exist_ok=True)
        self.nom_table = nom_table
        self.dimension = dimension
        self._db = lancedb.connect(str(self.chemin))
        self._table = self._ouvrir_ou_creer()

    def _schema(self) -> pa.Schema:
        return pa.schema([
            pa.field("id", pa.string()),
            pa.field("vecteur", pa.list_(pa.float32(), self.dimension)),
            pa.field("metadonnees", pa.string()),   # JSON
        ])

    def _ouvrir_ou_creer(self):
        # exist_ok=True : ouvre la table si elle existe, la cree sinon.
        return self._db.create_table(
            self.nom_table,
            schema=self._schema(),
            exist_ok=True,
        )

    def ajouter(self, elements: list[ElementIndexe]) -> None:
        if not elements:
            return
        import json
        lignes: list[dict[str, Any]] = []
        for e in elements:
            if len(e.vecteur) != self.dimension:
                raise ValueError(
                    f"Vecteur dimension {len(e.vecteur)} != {self.dimension}"
                )
            lignes.append({
                "id": e.id,
                "vecteur": list(e.vecteur),
                "metadonnees": json.dumps(e.metadonnees, ensure_ascii=False),
            })
        self._table.add(lignes)

    def rechercher(
        self, vecteur: list[float], k: int = 5
    ) -> list[ResultatRecherche]:
        if k <= 0:
            raise ValueError("k doit etre > 0")
        if self.taille() == 0:
            return []
        import json
        resultats = (
            self._table.search(list(vecteur)).limit(k).to_list()
        )
        sortie: list[ResultatRecherche] = []
        for r in resultats:
            sortie.append(
                ResultatRecherche(
                    id=r["id"],
                    score=float(r.get("_distance", 0.0)),
                    metadonnees=json.loads(r["metadonnees"]),
                )
            )
        return sortie

    def taille(self) -> int:
        return self._table.count_rows()

    def vider(self) -> None:
        self._db.drop_table(self.nom_table)
        self._table = self._db.create_table(self.nom_table, schema=self._schema())
