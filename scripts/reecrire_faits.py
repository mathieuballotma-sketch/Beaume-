"""Reecrit des faits juridiques en style client.

Fournisseurs supportes :
- groq   : API Groq (rapide, quota journalier limite)
- ollama : Ollama local (fournisseur par defaut)

Reserve aux donnees publiques ou synthetiques, jamais aux dossiers clients.
L'option de confirmation pour Groq est declarative, pas un audit du contenu.

Usage :
    PYTHONPATH=. python scripts/reecrire_faits.py --n 1000 --graine 43 \\
        --sortie data/training/faits_clients_2.jsonl \\
        --modele openai/gpt-oss-20b --fournisseur groq \\
        --confirmer-donnees-publiques-ou-synthetiques

    PYTHONPATH=. python scripts/reecrire_faits.py --n 1000 --graine 44 \\
        --sortie data/training/faits_clients_3.jsonl \\
        --modele qwen2.5:7b-instruct --fournisseur ollama
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path

from beaume.config import paths
from beaume.utils.logging import get_logger

log = get_logger("reecrire_faits")

MODELE_GROQ = "openai/gpt-oss-20b"
MODELE_OLLAMA = "qwen2.5:7b-instruct"
CHEMIN_PAIRES = paths.DATA / "training" / "paires.jsonl"
CHEMIN_SORTIE = paths.DATA / "training" / "faits_clients.jsonl"
OLLAMA_URL = "http://localhost:11434/v1"

PROMPT_SYSTEME = """Tu transformes un extrait de jugement en lettre
qu'un client ecrit a son avocat.

Tu n'es PAS un juriste. Tu es un justiciable. Tu ne connais AUCUN
article de loi. Tu ne connais AUCUN terme juridique. Tu racontes
ton histoire comme tu la raconterais a un ami.

REGLES ABSOLUES, dans cet ordre de priorite :

1. LONGUEUR : 150 a 300 mots MAXIMUM. C'est la regle la plus
   importante. Si tu depasses, tu as echoue. Compte mentalement.

2. LANGAGE CLIENT. Interdit absolument d'utiliser ces mots ou leurs
   variantes : requalification, requalifie, resilie, resiliation,
   sans cause reelle et serieuse, prud'hommes (sauf "j'ai ete aux
   prud'hommes" en langage courant), juridiction, instance, demande
   reconventionnelle, appelant, intimé, arret, jugement, decision,
   condamne, condamnation, dispositions, obligation de securite,
   faute grave, licenciement economique, rupture conventionnelle,
   solliciter, requerir, aux termes de, en l'espece, attendu que,
   par ailleurs, en consequence, en tout etat de cause, en outre.

3. PAS DE MONTANTS PRECIS. Un client ne connait pas 365,40 €.
   Arrondis (300 €, 5 000 €, 15 000 €) ou dis "un peu", "beaucoup",
   "plusieurs milliers d'euros". Si tu ne sais pas arrondir, omets.

4. PAS DE STRUCTURE. Pas de liste a puces. Pas de tirets. Pas de
   numeros. Pas de sous-titres. Le client ecrit un bloc continu,
   comme un mail.

5. PAS DE NARRATION JUDICIAIRE. Ne raconte PAS le deroulement de la
   procedure etape par etape. Le client ne dit pas "le 16 juin 2022
   le conseil a rendu un jugement qui...". Il dit "j'ai ete aux
   prud'hommes, ils m'ont donne un peu d'argent mais pas assez".

6. GARDE les faits essentiels : metier, employeur (nom), dates
   importantes (embauche, licenciement), ce qui s'est passe, ce que
   le client veut. C'est tout. 90 % du reste est du detail juridique
   qui doit disparaitre.

7. Premiere personne. "je", "mon", "j'ai". Le client parle.

8. Termine par une question simple a l'avocat.

EXEMPLE DE CE QU'IL FAUT FAIRE :

Original (extrait long) :
"M. [J] a ete embauche le 12 octobre 2018 par la SAS AC transport
en qualite de chauffeur routier zone courte. Par avenant du 1er
janvier 2020, il s'est vu attribuer la qualite de conducteur zone
longue et la duree hebdomadaire a ete portee de 35 heures a 200
heures par mois. Le 22 fevrier 2021, M. [J] a ete convoque a un
entretien prealable a un eventuel licenciement avec mise a pied
conservatoire. Par lettre du 12 avril 2021, il a pris acte de la
rupture. Par jugement du 16 juin 2022, le conseil de prud'hommes de
Montelimar a requalifie la prise d'acte en licenciement sans cause
reelle et serieuse et condamne la SAS AC transport a verser
3 500 € d'heures supplementaires, 350 € de conges payes, 15 600 €
de dommages pour travail dissimule, 5 200 € de preavis, 7 800 €
pour licenciement sans cause, 5 000 € pour harcelement."

Reecriture attendue :
"Bonjour Maitre, je travaillais comme chauffeur routier dans la
societe AC transport depuis 2018. Au debut je faisais des courtes
distances, puis en 2020 mon patron m'a fait passer sur des longs
trajets et m'a fait bosser beaucoup plus, presque 200 heures par
mois. J'ai eu un arret maladie, et quand je suis revenu ils m'ont
convoque a un entretien et m'ont mis a pied. Du coup j'ai decide
d'arreter et j'ai ete aux prud'hommes. Ils m'ont donne un peu
d'argent pour les heures supp et un peu pour le harcelement, mais
je trouve que c'est pas assez par rapport a tout ce que j'ai subi.
Est-ce que je peux faire appel ?"

REGLE FINALE : la reecriture ci-dessus fait 130 mots. C'est le bon
format. Si ta sortie fait plus de 350 mots, recommence.

Reponds UNIQUEMENT avec le texte reecrit."""


def _charger_env() -> dict[str, str]:
    env_path = paths.ROOT / ".env"
    if not env_path.exists():
        raise SystemExit(f".env introuvable : {env_path}")
    for ligne in env_path.read_text(encoding="utf-8").split("\n"):
        if "=" in ligne and not ligne.startswith("#"):
            k, v = ligne.split("=", 1)
            os.environ[k.strip()] = v.strip()
    return dict(os.environ)


def _creer_client(fournisseur: str, env: dict[str, str]):
    if fournisseur == "groq":
        from groq import Groq
        cle = env.get("GROQ_API_KEY", "")
        if not cle:
            raise SystemExit("GROQ_API_KEY absente du .env")
        return Groq(api_key=cle)
    if fournisseur == "ollama":
        from openai import OpenAI
        return OpenAI(base_url=OLLAMA_URL, api_key="ollama", timeout=600.0)
    raise SystemExit(f"Fournisseur inconnu : {fournisseur}")


def _charger_paires(limite: int | None, graine: int) -> list[dict]:
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


def _charger_deja_traitees(chemin: Path) -> set[str]:
    if not chemin.exists():
        return set()
    ids = set()
    with chemin.open(encoding="utf-8") as f:
        for ligne in f:
            try:
                d = json.loads(ligne)
                ids.add(d["id"])
            except Exception:
                continue
    return ids


def _reecrire(client, faits: str, modele: str,
              fournisseur: str, retries: int = 3) -> str | None:
    kwargs = {}
    if fournisseur == "groq" and "gpt-oss" in modele:
        kwargs["reasoning_effort"] = "low"
    for tentative in range(retries):
        try:
            reponse = client.chat.completions.create(
                model=modele,
                messages=[
                    {"role": "system", "content": PROMPT_SYSTEME},
                    {"role": "user", "content": faits[:4000]},
                ],
                max_tokens=2000,
                temperature=0.7,
                **kwargs,
            )
            texte = reponse.choices[0].message.content or ""
            texte = texte.strip()
            if len(texte) < 100:
                log.warning("Reponse trop courte (%d car.)", len(texte))
                continue
            return texte
        except Exception as e:
            log.warning("Erreur tentative %d : %s", tentative + 1, type(e).__name__)
            time.sleep(2 ** tentative)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--graine", type=int, default=42)
    parser.add_argument("--sortie", type=Path, default=CHEMIN_SORTIE)
    parser.add_argument("--fournisseur", type=str, default="ollama",
                        choices=["groq", "ollama"])
    parser.add_argument(
        "--confirmer-donnees-publiques-ou-synthetiques", action="store_true",
        help="Declaration obligatoire pour Groq : sources publiques ou synthetiques "
             "autorisees a cet usage, sans document client. Ne verifie pas le contenu.",
    )
    parser.add_argument("--modele", type=str, default=None)
    args = parser.parse_args()

    if (args.fournisseur == "groq"
            and not args.confirmer_donnees_publiques_ou_synthetiques):
        parser.error("Groq transmet les faits a un service externe. Confirmez "
                     "leur origine avec --confirmer-donnees-publiques-ou-synthetiques. "
                     "Les documents clients sont interdits.")

    if args.modele is None:
        args.modele = (MODELE_GROQ if args.fournisseur == "groq"
                       else MODELE_OLLAMA)

    env = _charger_env() if args.fournisseur == "groq" else {}
    client = _creer_client(args.fournisseur, env)

    if not CHEMIN_PAIRES.exists():
        raise SystemExit(f"Introuvable : {CHEMIN_PAIRES}")

    with CHEMIN_PAIRES.open("rb") as source:
        source_sha256 = hashlib.file_digest(source, "sha256").hexdigest()

    paires = _charger_paires(args.n, args.graine)
    deja_traitees = _charger_deja_traitees(args.sortie)

    print(f"Deja traitees : {len(deja_traitees)}")
    print(f"A traiter     : {len(paires)}")
    print(f"Fournisseur   : {args.fournisseur}")
    print(f"Modele        : {args.modele}")
    print(f"Sortie        : {args.sortie}")
    print()

    args.sortie.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    n_ok = 0
    n_echec = 0
    n_skip = 0

    with args.sortie.open("a", encoding="utf-8") as f_out:
        for i, paire in enumerate(paires, 1):
            if paire["id"] in deja_traitees:
                n_skip += 1
                continue

            texte_client = _reecrire(
                client, paire["faits"], args.modele,
                args.fournisseur,
            )
            if texte_client is None:
                n_echec += 1
                continue

            resultat = {
                "id": paire["id"],
                "date": paire["date"],
                "articles": paire["articles"],
                "faits_juridiques": paire["faits"][:2000],
                "faits_client": texte_client,
                "provenance_generation": {
                    "fournisseur": args.fournisseur,
                    "modele": args.modele,
                    "source_fichier": CHEMIN_PAIRES.name,
                    "source_sha256": source_sha256,
                    "origine_publique_ou_synthetique_declaree":
                        args.confirmer_donnees_publiques_ou_synthetiques,
                    "statut": "genere_auto_non_valide_juridiquement",
                },
            }
            f_out.write(json.dumps(resultat, ensure_ascii=False) + "\n")
            f_out.flush()
            n_ok += 1

            if i % 10 == 0:
                duree = time.monotonic() - t0
                vitesse = n_ok / duree * 60 if duree > 0 else 0
                print(f"  {i}/{len(paires)} — "
                      f"{n_ok} ok, {n_echec} echec, "
                      f"{vitesse:.1f}/min", flush=True)

    duree = time.monotonic() - t0
    print()
    print("=== Resultats ===")
    print(f"Reecrites  : {n_ok}")
    print(f"Echecs     : {n_echec}")
    print(f"Skippees   : {n_skip}")
    print(f"Duree      : {duree:.0f} s")
    print(f"Fournisseur: {args.fournisseur}")
    print(f"Modele     : {args.modele}")
    print(f"Sortie     : {args.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
