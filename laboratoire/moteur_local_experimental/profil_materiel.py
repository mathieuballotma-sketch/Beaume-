"""profil_materiel.py — Détection matérielle et choix de configuration.

Cibles : Mac Apple Silicon d'abord ; Mac Intel signalés comme support partiel
à qualifier par mesure. Plancher 16 Go de RAM totale.

Contrat :
- ne suppose PAS que la taille du fichier modèle = RAM consommée ;
- refuse si la marge de sécurité est insuffisante ;
- retourne un profil explicite (contexte, n_gpu_layers, threads, max_tokens) ;
- rend visibles les cas « non supporté » et « support partiel ».

Aucune mesure de consommation réelle n'est faite ici : ce module produit une
configuration candidate. La mesure viendra d'un test avec modèle réel.
"""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional

PLANCHER_RAM_GO = 16.0
MARGE_OS_GO_PETIT = 5.0
MARGE_OS_GO_GRAND = 6.0
FACTEUR_KV = 1.3


class MaterielInsuffisant(RuntimeError):
    """RAM totale < plancher 16 Go : hors périmètre produit."""


class ConfigurationRefusee(RuntimeError):
    """La configuration demandée dépasserait la marge de sécurité."""


@dataclass(frozen=True)
class Materiel:
    total_go: float
    disponible_go: Optional[float]
    ncpu: int
    arch: str
    modele_mac: str
    systeme: str


@dataclass(frozen=True)
class Profil:
    contexte: int
    n_gpu_layers: int
    threads: int
    max_tokens: int
    statut_support: str
    notes: str


def _run(cmd: list[str]) -> Optional[str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
        if r.returncode == 0:
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def detecter_materiel() -> Materiel:
    systeme = "macos" if platform.system() == "Darwin" else (
        "linux" if platform.system() == "Linux" else (
            "windows" if platform.system() == "Windows" else "inconnu"))
    arch = "inconnu"
    if platform.machine() == "arm64":
        arch = "arm64"
    elif platform.machine() in ("x86_64", "i386"):
        arch = "intel"

    total_go = 0.0
    dispo_go = None
    ncpu = os.cpu_count() or 1
    modele_mac = ""

    if systeme == "macos":
        brut = _run(["sysctl", "-n", "hw.memsize"])
        if brut and brut.isdigit():
            total_go = int(brut) / (1024 ** 3)
        brut = _run(["sysctl", "-n", "hw.ncpu"])
        if brut and brut.isdigit():
            ncpu = int(brut)
        brut = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if brut:
            modele_mac = brut
        vmstat = _run(["vm_stat"])
        if vmstat:
            page_size = 16384
            for ligne_vm in vmstat.splitlines():
                if 'page size of' in ligne_vm:
                    try:
                        page_size = int(
                            ligne_vm.split('page size of')[1]
                            .split('bytes')[0].strip()
                        )
                    except (ValueError, IndexError):
                        pass
                    break
            compteurs = {}
            for ligne_vm in vmstat.splitlines():
                if ':' in ligne_vm:
                    cle, val = ligne_vm.split(':', 1)
                    val = val.strip().rstrip('.')
                    if val.isdigit():
                        compteurs[cle.strip()] = int(val)
            if compteurs:
                pages_dispo = (
                    compteurs.get('Pages free', 0)
                    + compteurs.get('Pages inactive', 0)
                    + compteurs.get('Pages speculative', 0)
                    + compteurs.get('Pages purgeable', 0)
                )
                dispo_go = (pages_dispo * page_size) / (1024 ** 3)
    elif systeme == "linux":
        try:
            with open("/proc/meminfo") as f:
                for ligne in f:
                    if ligne.startswith("MemTotal:"):
                        total_go = int(ligne.split()[1]) / (1024 ** 2)
                    elif ligne.startswith("MemAvailable:"):
                        dispo_go = int(ligne.split()[1]) / (1024 ** 2)
        except OSError:
            pass

    return Materiel(
        total_go=round(total_go, 2),
        disponible_go=round(dispo_go, 2) if dispo_go else None,
        ncpu=ncpu, arch=arch, modele_mac=modele_mac, systeme=systeme,
    )


def qualifier(materiel: Materiel) -> str:
    if materiel.total_go < PLANCHER_RAM_GO - 0.5:
        return "non_supporte"
    if materiel.arch == "intel":
        return "support_partiel"
    return "ok"


def choisir_profil(
    materiel: Materiel,
    taille_fichier_modele_go: float,
    *,
    contexte_prefere: Optional[int] = None,
) -> Profil:
    if materiel.total_go < PLANCHER_RAM_GO - 0.5:
        raise MaterielInsuffisant(
            f"RAM totale {materiel.total_go} Go < plancher {PLANCHER_RAM_GO} Go"
        )
    statut = "support_partiel" if materiel.arch == "intel" else "ok"
    marge = MARGE_OS_GO_PETIT if materiel.total_go < 24.0 else MARGE_OS_GO_GRAND
    dispo_estimee = materiel.total_go - marge
    besoin_estime = taille_fichier_modele_go * FACTEUR_KV
    if besoin_estime > dispo_estimee:
        raise ConfigurationRefusee(
            f"Modèle {taille_fichier_modele_go} Go x {FACTEUR_KV} = "
            f"{besoin_estime:.1f} Go dépasse la marge libre ({dispo_estimee:.1f} Go)"
        )
    if (materiel.disponible_go is not None
            and materiel.disponible_go < besoin_estime + 1.5):
        raise ConfigurationRefusee(
            f"RAM disponible ({materiel.disponible_go:.1f} Go) insuffisante "
            f"pour {taille_fichier_modele_go:.1f} Go + KV ({besoin_estime:.1f} Go) "
            f"+ marge 1.5 Go. Libérer de la mémoire ou choisir un modèle plus petit."
        )
    # Refus si la RAM RÉELLEMENT disponible ne couvre pas le besoin + marge
    if (materiel.disponible_go is not None
            and materiel.disponible_go < besoin_estime + 1.5):
        raise ConfigurationRefusee(
            f"RAM disponible ({materiel.disponible_go:.1f} Go) insuffisante "
            f"pour {taille_fichier_modele_go:.1f} Go + KV ({besoin_estime:.1f} Go) "
            f"+ marge 1.5 Go. Libérer de la mémoire ou choisir un modèle plus petit."
        )
    if contexte_prefere is not None:
        contexte = contexte_prefere
    elif materiel.total_go < 20:
        contexte = 2048
    elif materiel.total_go < 28:
        contexte = 4096
    else:
        contexte = 8192
    max_tokens = min(1024, contexte // 4)
    n_gpu_layers = 99 if materiel.arch == "arm64" else 0
    threads = max(1, materiel.ncpu - 1)
    notes = []
    if statut == "support_partiel":
        notes.append("Mac Intel : support partiel, non qualifié par mesure")
    if materiel.disponible_go is not None and materiel.disponible_go < besoin_estime + 2.0:
        notes.append(
            f"RAM disponible estimée {materiel.disponible_go:.1f} Go "
            f"proche du besoin {besoin_estime:.1f} Go : risque de swap"
        )
    return Profil(
        contexte=contexte, n_gpu_layers=n_gpu_layers, threads=threads,
        max_tokens=max_tokens, statut_support=statut,
        notes=" ; ".join(notes) if notes else "configuration candidate",
    )
