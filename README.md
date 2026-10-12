# Beaume

Assistant juridique 100 % local pour avocats.
Aucune donnée client ne quitte jamais la machine.

## Philosophie

- Souveraineté totale : tout tourne localement.
- Traçabilité : chaque action est journalisée.
- Sécurité : validation d'entrée, machine à états, audit trail.
- Fiabilité : le vérificateur de citations empêche les hallucinations.
- Assistance, pas remplacement : l'IA prépare, l'avocat décide.

## État du projet

| Phase | Description | État |
|---|---|---|
| 0 | Fondations | Terminé |
| 7a/7b/7c | Ports LLM + chercheur + analyse | Terminé |
| 1 | Extracteur PDF | Terminé |
| 2 | Lecteur de dossier | Terminé |
| 3 | Chunker | Terminé |
| 4 | Chunking intégré | Terminé |
| 5a | Encodeur | Terminé |
| 5b | Index vectoriel | Terminé |
| 5c | Pipeline d'ingestion | Terminé |
| 6 | Corpus légal | Terminé |
| 7 | RAG | Terminé |
| 8 | Vérificateur de citations | Terminé |
| 9 | Génération de document | Terminé |

Tests : 200 passed, 0 skipped.

## Architecture

6 lois d'architecture strictes :

1. Dépendance descendante.
2. Conservation de l'information.
3. Tiers exclu (machine à états fermée).
4. Inversion des dépendances (Ports + Adapters).
5. Composition fermée.
6. Pureté au coeur, effets aux bords.

## Installation

    python3.12 -m venv .venv
    source .venv/bin/activate
    pip install -e .

## Lancer les tests

    source .venv/bin/activate
    pytest -v

## Licence

À définir.
