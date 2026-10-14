"""Reecrit des faits juridiques en style client via l'API Groq.

Le dataset paires.jsonl contient des faits rediges par des juges
(langage juridique). Un vrai dossier client est en langage courant.
Ce script reecrit chaque fait en style client.

Usage :
    PYTHONPATH=. python scripts/reecrire_faits.py --n 100
    PYTHONPATH=. python scripts/reecrire_faits.py --n 1000
    PYTHONPATH=. python scripts/reecrire_faits.py --n 1000 --graine 42

Reprise : si le script est interrompu, relance-le. Il reprend ou il
s'est arrete (les deja-traitees sont skippees).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

from groq import Groq

from beaume.config import paths
from beaume.utils.logging import get_logger

log = get_logger("reecrire_faits")

MODELE = "openai/gpt-oss-120b"
CHEMIN_PAIRES = paths.DATA / "training" / "paires.jsonl"
CHEMIN_SORTIE = paths.DATA / "training" / "faits_clients.jsonl"

PROMPT_SYSTEME = """Tu es un assistant qui reformule des faits
juridiques en langage client.

Regles ABSOLUES :
1. Tu recois un texte de decision de justice (faits bruts).
2. Tu le reecris comme si le client ecrivait LUI-MEME a son avocat.
3. Premiere personne obligatoire ("je", "mon employeur", "j'ai ete").
4. Garde TOUS les elements factuels : dates, lieux, noms de societes,
   montants, durees, fonctions.
5. N'invente RIEN. Si une info manque, tant pis.
6. INTERDICTION ABSOLUE de citer un article de loi. Si le texte
   original cite "l'article L1233-3" ou "l'article 8 du contrat",
   NE LE RECOPIE PAS. Un client normal ne connait pas ces references.
7. N'utilise PAS de vocabulaire juridique (pas de "attendu que",
   "aux termes de", "en l'espece", "le requerant", "la cour",
   "le jugement", "les dispositions").
8. Longueur : 200-400 mots maximum. Sois concis.
9. Style : simple, direct, parfois confus. Le client n'est pas un
   redacteur professionnel. Il peut repeter, hesiter, digresser un peu.
10. Termine par une question ou une demande claire a l'avocat.

Exemple de transformation :

ORIGINAL :
"Attendu que Mme X a ete engagee le 1er mars 2000 par la societe Y
en qualite de secretaire ; qu'elle a ete licenciee le 15 juin 2023
pour motif economique ; que l'employeur invoquait des difficultes
economiques liees a une baisse du chiffre d'affaires."

REECRITURE :
"Bonjour Maitre, j'ai travaille comme secretaire dans la societe Y
depuis mars 2000. Le 15 juin 2023, mon patron m'a licenciee en disant
que l'entreprise avait des difficultes et que le chiffre d'affaires
avait baisse. Mais moi je trouve ca bizarre parce que..."

Reponds UNIQUEMENT avec le texte reecrit. Pas de commentaire.
Pas de guillemets. Pas de titre."""


def _charger_env() -> str:
    """Charge GROQ_API_KEY depuis .env."""
    env_path = paths.ROOT / ".env"
    if not env_path.exists():
        raise SystemExit(f".env introuvable : {env_path}")
    for ligne in env_path.read_text(encoding="utf-8").split("\n"):
        if "=" in ligne and not ligne.startswith("#"):
            k, v = ligne.split("=", 1)
            os.environ[k.strip()] = v.strip()
    cle = os.environ.get("GROQ_API_KEY", "")
    if not cle:
        raise SystemExit("GROQ_API_KEY absente du .env")
    return cle


def _charger_paires(limite: int | None, graine: int) -> list[dict]:
    """Charge paires.jsonl avec echantillonnage stratifie."""
    from collections import defaultdict

    toutes = []
    with CHEMIN_PAIRES.open(encoding="utf-8") as f:
        for ligne in f:
            toutes.append(json.loads(ligne))

    print(f"Paires chargees : {len(toutes)}")

    par_article: dict[str, list[dict]] = defaultdict(list)
    for p in toutes:
        if p["articles"]:
            par_article[p["articles"][0]].append(p)

    groupes = sorted(par_article.items(), key=lambda x: -len(x[1]))
    print(f"Articles distincts : {len(groupes)}")

    if limite is None:
        return toutes

    random.seed(graine)
    echantillon = []
    for article, paires in groupes:
        random.shuffle(paires)
        echantillon.extend(paires[:20])
        if len(echantillon) >= limite * 2:
            break

    random.shuffle(echantillon)
    return echantillon[:limite]


def _charger_deja_traitees() -> set[str]:
    """Retourne les IDs deja traites (pour reprise)."""
    if not CHEMIN_SORTIE.exists():
        return set()
    ids = set()
    with CHEMIN_SORTIE.open(encoding="utf-8") as f:
        for ligne in f:
            try:
                d = json.loads(ligne)
                ids.add(d["id"])
            except Exception:
                continue
    return ids


def _reecrire(client: Groq, faits: str, retries: int = 3) -> str | None:
    """Appelle Groq pour reecrire les faits. Retourne None si echec."""
    for tentative in range(retries):
        try:
            reponse = client.chat.completions.create(
                model=MODELE,
                messages=[
                    {"role": "system", "content": PROMPT_SYSTEME},
                    {"role": "user", "content": faits[:4000]},
                ],
                max_tokens=2000,
                temperature=0.7,
            )
            texte = reponse.choices[0].message.content or ""
            texte = texte.strip()
            if len(texte) < 100:
                log.warning("Reponse trop courte (%d car.)", len(texte))
                continue
            return texte
        except Exception as e:
            log.warning("Erreur tentative %d : %s", tentative + 1, e)
            time.sleep(2 ** tentative)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100,
                        help="Nombre de paires a traiter.")
    parser.add_argument("--graine", type=int, default=42)
    args = parser.parse_args()

    cle = _charger_env()
    client = Groq(api_key=cle)

    if not CHEMIN_PAIRES.exists():
        raise SystemExit(f"Introuvable : {CHEMIN_PAIRES}")

    paires = _charger_paires(args.n, args.graine)
    deja_traitees = _charger_deja_traitees()

    print(f"Deja traitees : {len(deja_traitees)}")
    print(f"A traiter     : {len(paires)}")
    print()

    CHEMIN_SORTIE.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    n_ok = 0
    n_echec = 0
    n_skip = 0

    with CHEMIN_SORTIE.open("a", encoding="utf-8") as f_out:
        for i, paire in enumerate(paires, 1):
            if paire["id"] in deja_traitees:
                n_skip += 1
                continue

            texte_client = _reecrire(client, paire["faits"])
            if texte_client is None:
                n_echec += 1
                continue

            resultat = {
                "id": paire["id"],
                "date": paire["date"],
                "articles": paire["articles"],
                "faits_juridiques": paire["faits"][:2000],
                "faits_client": texte_client,
            }
            f_out.write(json.dumps(resultat, ensure_ascii=False) + "\n")
            f_out.flush()
            n_ok += 1

            if i % 10 == 0:
                duree = time.monotonic() - t0
                vitesse = n_ok / duree * 60 if duree > 0 else 0
                print(f"  {i}/{len(paires)} — "
                      f"{n_ok} ok, {n_echec} echec, "
                      f"{vitesse:.1f}/min")

    duree = time.monotonic() - t0
    print()
    print("=== Resultats ===")
    print(f"Reecrites  : {n_ok}")
    print(f"Echecs     : {n_echec}")
    print(f"Skippees   : {n_skip}")
    print(f"Duree      : {duree:.0f} s")
    print(f"Sortie     : {CHEMIN_SORTIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())