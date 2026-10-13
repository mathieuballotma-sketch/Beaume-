# Beaume

Assistant juridique 100 % local pour avocats.

Beaume extrait, analyse et vérifie les citations juridiques d'un dossier
client. Toute donnée reste sur la machine — aucune information ne quitte
jamais le poste de travail.

---

## Philosophie

- **Souveraineté totale** — tout tourne localement, aucun appel réseau.
- **Traçabilité** — chaque action journalisée, chaque citation vérifiable.
- **Fiabilité** — un vérificateur confronte chaque citation proposée au
  corpus officiel.
- **Assistance, pas remplacement** — l'IA prépare, l'avocat décide.

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

Suite complète : **231 tests, ~26 secondes**.

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
- Vérificateur de citations : 5 verdicts (`VALIDE`, `INTROUVABLE`,
  `VERSION_INCORRECTE`, `ABROGE`, `TEXTE_DIFFERENT`).
- Corpus réel : 25 767 articles (Code travail, civil, sécurité sociale,
  procédure civile, consommation).
- Normalisation des numéros DILA ⇄ format humain.
- Recherche FTS5 : rappel@1 = 93 %, rappel@5 = 99 %, 7 ms par requête.
- Script de téléchargement de corpus idempotent.
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
- **LLM non déterministe** — la température n'est pas encore fixée ;
  deux analyses d'un même dossier peuvent différer.
- **Corpus de test réduit** — le pipeline n'a jamais tourné sur un
  dossier de 50-100 pages représentatif de la pratique réelle.
- **Extraction PDF partielle** — les PDFs scannés (sans couche texte),
  chiffrés ou corrompus ne sont pas pris en charge.

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