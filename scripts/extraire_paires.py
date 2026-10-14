"""Extrait des paires (faits, articles) depuis les decisions de justice.

Pour chaque decision :
  1. Extrait le texte entre FAITS ET PROCEDURE et PAR CES MOTIFS.
  2. Extrait tous les articles du Code du travail cites.
  3. Si les deux sont presents -> ecrit une paire dans le JSONL.

Usage :
    PYTHONPATH=. python scripts/extraire_paires.py --limite 100
    PYTHONPATH=. python scripts/extraire_paires.py --toutes
    PYTHONPATH=. python scripts/extraire_paires.py --sortie data/training/paires.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from datasets import load_from_disk

from beaume.config import paths
from beaume.utils.logging import get_logger

log = get_logger("extraire_paires")

# Marqueurs de debut de faits (ordre de priorite)
MARQUEURS_DEBUT = [
    r"FAITS\s+ET\s+PROC[EÉ]DURE",
    r"FAITS\s+ET\s+MOYENS",
    r"EXPOS[EÉ]\s+DU\s+LITIGE",
    r"EXPOSE\s+DU\s+LITIGE",
    r"RAPPEL\s+DES\s+FAITS",
    r"RAPPEL\s+DES\s+FAITS\s+ET\s+DE\s+LA\s+PROC[EÉ]DURE",
    r"PR[EÉ]TENTIONS\s+DES\s+PARTIES",
    r"MOYENS\s+DES\s+PARTIES",
    r"ANTEC[EÉ]DENTS",
    r"DEBATS",
]

# Marqueurs de fin de faits
MARQUEURS_FIN = [
    r"PAR\s+CES\s+MOTIFS",
    r"MOTIFS?\s+DE\s+LA\s+D[EÉ]CISION",
    r"R[EÉ]PONSE\s+DE\s+LA\s+COUR",
    r"DISPOSITIF",
]

# Marqueurs d'articles (assez permissif)
MARQUEURS_ARTICLE = [
    r"Vu\s+l'article\s+([A-Z]?\s*\.?\s*\d+(?:-\d+)*(?:-\d+)*)",
    r"Vu\s+les\s+articles\s+([A-Z]?\s*\.?\s*\d+(?:-\d+)*(?:-\d+)*)",
    r"l'article\s+([A-Z]?\s*\.?\s*\d+(?:-\d+)*(?:-\d+)*)",
    r"les\s+articles\s+([A-Z]?\s*\.?\s*\d+(?:-\d+)*(?:-\d+)*)",
]


def _nettoyer_numero(numero: str) -> str | None:
    """Normalise un numero d'article : 'L. 1233-3' -> 'L1233-3'.

    Regles :
      - Doit commencer par L, R, D ou A (sinon rejete).
      - Doit contenir au moins 3 chiffres (rejette 700, 12, 1382).
      - Le prefixe est toujours conserve.
    """
    num = numero.strip()
    num = re.sub(r"\s+", "", num)
    if not num:
        return None
    # Prefixe OBLIGATOIRE (L, R, D, A) : les articles de codes autres
    # (700, 1382, 12...) sont rejetes.
    if not re.match(r"^[LRDA]\d", num):
        return None
    # Au moins 3 chiffres apres le prefixe
    chiffres = re.sub(r"[^0-9]", "", num)
    if len(chiffres) < 3:
        return None
    return num


def _extraire_faits(texte: str) -> str | None:
    """Extrait la section FAITS ET PROCEDURE."""
    # Trouver le marqueur de debut
    debut = None
    for m in MARQUEURS_DEBUT:
        match = re.search(m, texte, re.IGNORECASE)
        if match:
            debut = match.end()
            break

    if debut is None:
        # Fallback : prendre un bloc central (position 1500-6000)
        # Apres l'en-tete (avocats, composition) et avant les motifs.
        if len(texte) < 3000:
            return None
        debut = 1500
        fin_fallback = min(1500 + 4500, len(texte))
        faits = texte[debut:fin_fallback].strip()
        faits = re.sub(r"\n{3,}", "\n\n", faits)
        if len(faits) < 200:
            return None
        return faits[:5000]

    # Trouver le marqueur de fin
    fin = None
    for m in MARQUEURS_FIN:
        match = re.search(m, texte[debut:], re.IGNORECASE)
        if match:
            fin = debut + match.start()
            break

    if fin is None:
        fin = min(debut + 5000, len(texte))

    faits = texte[debut:fin].strip()
    faits = re.sub(r"^\s*:?\s*", "", faits)
    faits = re.sub(r"\n{3,}", "\n\n", faits)
    faits = faits.strip()

    if len(faits) < 200:
        return None

    return faits[:5000]  # On tronque a 5000 car.


def _extraire_articles(texte: str) -> list[str]:
    """Extrait tous les numeros d'articles du Code du travail cites."""
    trouves = set()
    # On cherche dans tout le texte
    for marqueur in MARQUEURS_ARTICLE:
        for match in re.finditer(marqueur, texte, re.IGNORECASE):
            # Verifier que c'est bien dans un contexte 'code du travail'
            debut_contexte = max(0, match.start() - 50)
            fin_contexte = min(len(texte), match.end() + 80)
            contexte = texte[debut_contexte:fin_contexte].lower()
            if "code du travail" not in contexte and "code du trav" not in contexte:
                continue

            num = _nettoyer_numero(match.group(1))
            if num:
                trouves.add(num)

    return sorted(trouves)


def _traiter_decision(d: dict) -> dict | None:
    """Retourne une paire (faits, articles) ou None."""
    texte = d.get("text") or ""
    if len(texte) < 2000:
        return None

    if "code du travail" not in texte.lower():
        return None

    faits = _extraire_faits(texte)
    if faits is None:
        return None

    articles = _extraire_articles(texte)
    if not articles:
        return None

    return {
        "id": d.get("id", ""),
        "date": d.get("decision_date", ""),
        "juridiction": d.get("location", ""),
        "chambre": d.get("chamber", ""),
        "faits": faits,
        "articles": articles,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limite", type=int, default=None,
        help="Limite le nombre de decisions traitees (debug).",
    )
    parser.add_argument(
        "--toutes", action="store_true",
        help="Traite toutes les decisions 2015+.",
    )
    parser.add_argument(
        "--sortie", type=Path, default=paths.DATA / "training" / "paires.jsonl",
        help="Fichier JSONL de sortie.",
    )
    args = parser.parse_args()

    if not args.limite and not args.toutes:
        print("Precise --limite N ou --toutes.")
        return 1

    args.sortie.parent.mkdir(parents=True, exist_ok=True)

    print("Chargement des cours d'appel...")
    ds = load_from_disk(str(paths.LEGAL / "jurisprudence"))["cour_d_appel"]
    recentes = [
        d for d in ds
        if d["decision_date"] and d["decision_date"] >= "2015-01-01"
        and d["text"]
        and "code du travail" in d["text"].lower()
    ]
    print(f"Decisions disponibles : {len(recentes)}")

    if args.limite:
        recentes = recentes[:args.limite]
        print(f"Limite a : {len(recentes)}")

    print(f"Sortie : {args.sortie}")
    print()
    print("Extraction...")

    t0 = time.monotonic()
    n_total = 0
    n_paires = 0
    n_rejets = {"pas_faits": 0, "pas_articles": 0, "trop_court": 0}

    with args.sortie.open("w", encoding="utf-8") as f:
        for i, d in enumerate(recentes, 1):
            n_total += 1
            paire = _traiter_decision(d)
            if paire is None:
                # Diagnostic
                texte = d.get("text") or ""
                if len(texte) < 2000:
                    n_rejets["trop_court"] += 1
                elif "code du travail" not in texte.lower():
                    n_rejets["pas_articles"] += 1
                else:
                    n_rejets["pas_faits"] += 1
                continue

            f.write(json.dumps(paire, ensure_ascii=False) + "\n")
            n_paires += 1

            if i % 500 == 0:
                duree = time.monotonic() - t0
                print(f"  {i}/{len(recentes)} — {n_paires} paires "
                      f"({duree:.0f}s)")

    duree = time.monotonic() - t0
    print()
    print("=== Resultats ===")
    print(f"Decisions traitees : {n_total}")
    print(f"Paires extraites   : {n_paires}")
    print(f"Taux               : {n_paires * 100 / n_total:.1f} %")
    print(f"Duree              : {duree:.0f} s")
    print()
    print("Rejets :")
    for raison, n in n_rejets.items():
        print(f"  {raison:15} : {n}")
    print()
    print(f"Fichier : {args.sortie}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
