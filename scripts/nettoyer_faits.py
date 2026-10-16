"""Nettoie les faits_clients pour l'entrainement.

Detecte et signale les paires qui contiennent :
- des termes de "style juge" (attendu que, en l'espece...)
- des montants a la virgule (ex: 3 859,40 euros)
- des longueurs hors cible (< 100 ou > 400 mots)

Les termes que le client peut citer en lisant son courrier
(faute grave, liquidation judiciaire, rupture conventionnelle)
sont ACCEPTES. Ils font partie du langage client reel.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CHEMIN_ENTREE = Path("data/training/faits_clients_final.jsonl")
CHEMIN_PROPRE = Path("data/training/faits_clients_propres.jsonl")
CHEMIN_REVOIR = Path("data/training/faits_clients_a_revoir.jsonl")

# Termes "juge" uniquement. Ce que le client ne dirait JAMAIS.
TERMES_NOIRS = [
    "requalif",
    "aux termes",
    "en l'espece",
    "attendu que",
    "par ailleurs",
    "en consequence",
    "en outre",
    "sollicit",
    "requer",
    "dispositions",
]

# Montant a la virgule : "3 859,40" ou "1 234,56"
REGEX_MONTANT_VIRGULE = re.compile(r"\d[\s\u202f]\d{3}[,.]\d{2}")

MIN_MOTS = 100
MAX_MOTS = 400


def _normaliser(texte: str) -> str:
    remplacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "î": "i", "ï": "i",
        "ô": "o", "ö": "o",
        "û": "u", "ü": "u",
        "ç": "c",
    }
    texte = texte.lower()
    for k, v in remplacements.items():
        texte = texte.replace(k, v)
    return texte


def _analyser(d: dict) -> tuple[bool, list[str]]:
    problemes: list[str] = []
    texte = _normaliser(d.get("faits_client", ""))

    for terme in TERMES_NOIRS:
        if terme in texte:
            problemes.append(f"terme:{terme}")

    if REGEX_MONTANT_VIRGULE.search(d.get("faits_client", "")):
        problemes.append("montant_virgule")

    n_mots = len(d.get("faits_client", "").split())
    if n_mots < MIN_MOTS:
        problemes.append(f"court:{n_mots}")
    elif n_mots > MAX_MOTS:
        problemes.append(f"long:{n_mots}")

    return (len(problemes) == 0, problemes)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entree", type=Path, default=CHEMIN_ENTREE)
    args = parser.parse_args()

    if not args.entree.exists():
        raise SystemExit(f"Introuvable : {args.entree}")

    n_total = 0
    n_propres = 0
    n_revoir = 0
    compteurs: dict[str, int] = {}

    with args.entree.open(encoding="utf-8") as f_in, \
         CHEMIN_PROPRE.open("w", encoding="utf-8") as f_ok, \
         CHEMIN_REVOIR.open("w", encoding="utf-8") as f_ko:
        for ligne in f_in:
            n_total += 1
            try:
                d = json.loads(ligne)
            except json.JSONDecodeError:
                continue

            ok, problemes = _analyser(d)
            if ok:
                f_ok.write(json.dumps(d, ensure_ascii=False) + "\n")
                n_propres += 1
            else:
                d["_problemes"] = problemes
                f_ko.write(json.dumps(d, ensure_ascii=False) + "\n")
                n_revoir += 1
                for p in problemes:
                    cle = p.split(":")[0]
                    compteurs[cle] = compteurs.get(cle, 0) + 1

    print()
    print("=== Nettoyage ===")
    print(f"Total       : {n_total}")
    print(f"Propres     : {n_propres} ({n_propres/n_total:.0%})")
    print(f"A revoir    : {n_revoir} ({n_revoir/n_total:.0%})")
    print()
    print("Problemes les plus frequents :")
    for cle, n in sorted(compteurs.items(), key=lambda x: -x[1]):
        print(f"  {cle:25s} : {n}")
    print()
    print(f"Propres     : {CHEMIN_PROPRE}")
    print(f"A revoir    : {CHEMIN_REVOIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())