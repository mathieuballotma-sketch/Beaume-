# Beaume

Assistant juridique 100 % local pour avocats.

Beaume extrait, analyse et vérifie les citations juridiques d'un dossier
client. Toute donnée reste sur la machine — aucune information ne quitte
jamais le poste de travail.

---

## Philosophie

- **Souveraineté totale** — une fois installé, Beaume fonctionne sans
  aucune connexion réseau.
- **Traçabilité** — chaque action journalisée, chaque citation vérifiable.
- **Fiabilité** — un vérificateur confronte chaque citation proposée au
  corpus officiel.
- **Assistance, pas remplacement** — l'IA prépare, l'avocat décide.

---

## Quand Internet est-il utilisé ?

La promesse de confidentialité de Beaume porte sur les **dossiers
clients**. Elle ne signifie pas que Beaume n'a jamais besoin d'Internet —
l'installation initiale et les mises à jour du corpus sont des moments
où le réseau est utilisé, mais **jamais pour transmettre des données
client**.

| Moment | Internet ? | Ce qui circule | Données client ? |
|---|---|---|---|
| Installation initiale (une fois) | Oui | Téléchargement du corpus légal public (~700 Mo) et des modèles de langage (`ollama pull`) | **Non** |
| Utilisation quotidienne (analyse d'un dossier) | **Non** | Rien | — |
| Mise à jour du corpus légal (occasionnelle) | Oui | Téléchargement d'une nouvelle version publique du corpus | **Non** |
| Mise à jour de Beaume (occasionnelle) | Oui | `git pull` ou installation d'un paquet Python | **Non** |

### Détail des moments réseau

**1. Installation initiale (une seule fois).**
Le corpus légal (dataset Hugging Face `VinceGx33/legi-french-law-2025`,
~700 Mo) et les modèles Ollama (`qwen2.5:7b-instruct`, `bge-m3`) sont
téléchargés depuis Internet. Ce sont des ressources **publiques** —
elles ne contiennent aucune donnée de dossier. Aucun fichier client
n'est lu pendant cette étape.

**2. Utilisation quotidienne (analyse d'un dossier).**
C'est le cœur du produit. Le PDF du client est lu localement, analysé
par un modèle de langage qui tourne sur la machine, et le rapport est
écrit sur le disque. **Aucune requête réseau n'est effectuée.**
Vous pouvez couper le Wi-Fi : Beaume fonctionne.

**3. Mise à jour du corpus légal (occasionnelle).**
Quand une nouvelle version du corpus est publiée (nouveaux textes,
rectifications), vous relancez `python scripts/telecharger_corpus.py`.
Le script télécharge uniquement des fichiers publics. Les dossiers
clients dans `data/inbox/` ne sont jamais lus ni envoyés.

**4. Mise à jour de Beaume (occasionnelle).**
`git pull` récupère les nouvelles versions du code. Aucune donnée
locale n'est transmise.

### Ce que Beaume ne fait pas

- Pas de télémétrie, pas de statistiques d'usage envoyées où que ce soit.
- Pas de compte utilisateur, pas de serveur central.
- Pas d'appel à une API LLM distante (OpenAI, Anthropic, Mistral…).
- Pas de synchronisation cloud des dossiers.
- Pas de vérification de licence en ligne (le jeton est vérifié
  localement).

### Ce que Beaume fait

- Lit les PDF locaux du dossier dans `data/inbox/`.
- Écrit les rapports dans `data/out/`.
- Écrit les journaux d'exécution dans `data/logs/`.
- Stocke le corpus légal dans `data/vector/legi_full.sqlite`.
- Sollicite Ollama **en local** (`http://localhost:11434`) pour la
  génération et l'encodage.

Tout reste sur votre Mac.

---

## Installation

Prérequis : Python 3.11+, ~1 Go d'espace disque, Ollama installé.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/telecharger_corpus.py
```

Le téléchargement du corpus représente environ 700 Mo (5 à 15 minutes
selon la connexion). Le script est idempotent : relancé, il ne fait rien.

Modèles Ollama requis :

```bash
ollama pull qwen2.5:7b-instruct
ollama pull bge-m3
```

---

## Utilisation

```bash
PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/mon_dossier
PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/mon_dossier 2024-01-01
```

Le rapport Markdown est écrit dans `data/out/<nom_dossier>_analyse.md`.

### Mode démo (5 articles, ~20 secondes)

Pour tester le pipeline sans télécharger le corpus complet :

```bash
BEAUME_CORPUS_DEMO=1 PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/mon_dossier
```

---

## Tests

```bash
pytest -v
```

Suite complète : **233 tests, ~26 secondes**.

---

## Architecture

6 lois non négociables :

1. **Dépendance descendante** : L5 → L4 → L3 → L2 → L1 → L0.
2. **Conservation de l'information** : chaque transformation traçable.
3. **Tiers exclu** : machine à états fermée, pas d'état intermédiaire.
4. **Inversion des dépendances** : Ports (`Protocol`) + Adapters.
5. **Composition fermée** : une porte d'entrée par module.
6. **Pureté au cœur, effets aux bords**.

### Structure

```
beaume/
├── legal/        L2  Ontologie juridique (zéro dépendance externe)
├── ports/        L1  Contrats (Protocol)
├── adapters/     L0  Implémentations (PDF, Ollama, SQLite, FTS5, HF)
├── application/  L3  Cas d'usage (pipeline, machine à états)
├── output/           Rendu Markdown
├── config/           Chemins
├── testing/          Doublures (index mémoire)
└── utils/            Logging, profiler, texte
```

### Règle d'extension

Ajouter une fonctionnalité = 1 fichier + 1 test + 0 modification du cœur.

---

## État du projet

### Fait

- Fondations, Git, GitHub.
- Ontologie juridique (23 codes + `CODE_AUTRE`).
- Machine à états : DÉPOSÉ → EXTRAIT → DÉCOUPÉ → INDEXÉ → ANALYSÉ →
  VÉRIFIÉ → PUBLIÉ.
- Ports + adaptateurs : PDF, Ollama (encodeur + générateur), LanceDB,
  SQLite/FTS5, HuggingFace LEGI.
- Pipeline complet dossier → Markdown.
- Vérificateur de citations : 6 verdicts (`VALIDE`, `INTROUVABLE`,
  `VERSION_INCORRECTE`, `ABROGE`, `TEXTE_DIFFERENT`, `EXTRAIT_MANQUANT`).
- Corpus réel : 25 767 articles (Code travail, civil, sécurité sociale,
  procédure civile, consommation).
- Normalisation des numéros DILA ⇄ format humain.
- Recherche FTS5 : rappel@1 = 93 %, rappel@5 = 99 %, 7 ms par requête.
- Script de téléchargement de corpus idempotent, testé sur base réelle.
- Déterminisme LLM : `temperature=0.0` dans tout le pipeline.
- Rapport Markdown exposant les citations rejetées avec extrait proposé
  et texte officiel.

### Limites connues

Ces limites sont documentées et suivies. Elles seront traitées avant
toute mise en production.

- **Pertinence non garantie** — le vérificateur confirme qu'un article
  existe et que son texte correspond, mais pas qu'il est juridiquement
  pertinent pour le dossier. Un article techniquement valide peut être
  hors sujet.
- **Corpus historique absent** — une seule version par article. Le
  traitement d'un dossier « en date des faits » antérieure à 2025 n'est
  pas encore possible.
- **Corpus de test réduit** — le pipeline n'a jamais tourné sur un
  dossier de 50-100 pages représentatif de la pratique réelle.
- **Extraction PDF partielle** — les PDFs scannés (sans couche texte),
  chiffrés ou corrompus ne sont pas pris en charge.
- **Pas de CI** — les tests ne sont pas exécutés automatiquement à
  chaque commit. Le corpus de 700 Mo rend l'hébergement d'un runner
  coûteux.

---

## Documentation

- [`docs/PROMPT_BEAUME.md`](docs/PROMPT_BEAUME.md) — vision et méthode.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — décisions actées.
- [`docs/JOURNAL.md`](docs/JOURNAL.md) — chronologie du projet.

---

## Données

Aucune donnée client n'est versionnée dans Git. Les répertoires suivants
sont ignorés :

- `data/inbox/` — dossiers clients.
- `data/out/` — rapports générés.
- `data/legal/` — corpus légal téléchargé.
- `data/vector/` — bases SQLite.
- `data/logs/` — journaux.

---

## Licence

À définir.