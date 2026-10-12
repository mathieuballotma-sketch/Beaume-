"""Profiler leger pour mesurer les temps par etape.

Zero dependance externe. Zero surcout en production (desactive par defaut).
Activation :
    - context manager : with profil_actif("ingestion") as p: ...
    - variable d'environnement : BEAUME_PROFILE=1
"""
from __future__ import annotations

import functools
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


# Pile des profils actifs (supporte l'imbrication)
_profils_actifs: list["Profil"] = []


def _profilage_actif() -> bool:
    return bool(_profils_actifs)


def chronometre(nom: str) -> Callable:
    """Decorateur : mesure le temps d'execution d'une fonction.

    Si aucun profil n'est actif, la fonction est appelee sans surcout.
    Sinon, le temps est enregistre dans tous les profils actifs.
    """
    def decorateur(fonction: Callable) -> Callable:
        @functools.wraps(fonction)
        def enveloppe(*args: Any, **kwargs: Any) -> Any:
            if not _profilage_actif():
                return fonction(*args, **kwargs)

            debut = time.perf_counter()
            try:
                return fonction(*args, **kwargs)
            finally:
                duree = time.perf_counter() - debut
                for profil in _profils_actifs:
                    profil.enregistrer(nom, duree)

        return enveloppe
    return decorateur


@dataclass
class Profil:
    """Collecte les temps d'execution par etape."""
    nom: str = "profil"
    mesures: dict[str, list[float]] = field(default_factory=dict)

    def enregistrer(self, etape: str, duree: float) -> None:
        self.mesures.setdefault(etape, []).append(duree)

    def total(self, etape: str) -> float:
        return sum(self.mesures.get(etape, []))

    def nombre(self, etape: str) -> int:
        return len(self.mesures.get(etape, []))

    def temps_total(self) -> float:
        return sum(sum(v) for v in self.mesures.values())

    def etapes(self) -> list[str]:
        return sorted(self.mesures.keys())

    def rapport(self) -> str:
        total = self.temps_total()
        lignes = [f"=== Profil : {self.nom} ==="]
        if not self.mesures:
            lignes.append("(aucune mesure)")
            return "\n".join(lignes)

        largeur = max(len(e) for e in self.mesures) + 2
        for etape in self.etapes():
            cumul = self.total(etape)
            n = self.nombre(etape)
            pourcent = (cumul / total * 100) if total > 0 else 0.0
            lignes.append(
                f"  {etape.ljust(largeur)} {cumul:8.3f} s "
                f"({pourcent:5.1f} %) x{n}"
            )
        lignes.append("-" * (largeur + 30))
        lignes.append(f"  {'TOTAL'.ljust(largeur)} {total:8.3f} s")
        return "\n".join(lignes)

    def vider(self) -> None:
        self.mesures.clear()


@contextmanager
def profil_actif(
    nom: str = "profil",
    profil: Profil | None = None,
) -> Iterator[Profil]:
    """Active le profilage dans le contexte courant.

    Usage :
        with profil_actif("ingestion") as p:
            ingestion.ingerer(dossier)
        print(p.rapport())
    """
    p = profil if profil is not None else Profil(nom=nom)
    _profils_actifs.append(p)
    try:
        yield p
    finally:
        _profils_actifs.pop()


def profilage_par_env() -> bool:
    """Verifie si la variable d'environnement active le profilage."""
    valeur = os.environ.get("BEAUME_PROFILE", "0")
    return valeur not in ("0", "", "false", "False")