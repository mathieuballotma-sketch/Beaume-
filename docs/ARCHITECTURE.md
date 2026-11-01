# Architecture du dépôt public

[Accueil](../README.md) · [Documentation](README.md)

Carte issue de la lecture de `main` à partir de `515edce`, le 27 octobre 2026.
Elle décrit les modules publiés ; les expériences locales du laboratoire ne
sont pas automatiquement présentes dans cette branche.

## Arborescence utile

```text
beaume/
  legal/         Articles, versions, citations, identifiants et normalisation
  ports/         Contrats des dépôts, extracteurs, générateurs et vérificateurs
  adapters/      PDF, Ollama, SQLite, FTS5, sources LEGI/DILA, index vectoriel
  application/   Lecture, découpage, sélection, analyse et pipeline
  output/        Rapport et rendu Markdown
  config/        Chemins de données
  bench/         Cas et métriques d’évaluation
  testing/       Doublures utilisées pour les tests
  utils/         Journaux et mesure des durées
scripts/         Points d’entrée et outils de préparation/évaluation
tests/          Tests unitaires, intégration et petites fixtures
docs/           Guides, protocoles, décisions et journaux historiques
data/           Ressources locales exclues de Git
```

## Chemin d’une analyse

| Étape | Fichiers principaux | Responsabilité |
| --- | --- | --- |
| Assemblage | `scripts/analyser_dossier.py` | Ouvrir le corpus, choisir le modèle, composer les dépendances |
| Orchestration | `beaume/application/pipeline.py` | Appeler l’analyse, puis le vérificateur, puis le rapport |
| Lecture | `beaume/application/lecteur_dossier.py`, `beaume/adapters/extracteur_pdf.py` | Extraire texte et pages des fichiers pris en charge |
| Découpage | `beaume/application/chunker.py`, `selecteur_chunks.py` | Préparer et sélectionner des passages |
| Recherche | `beaume/application/analyse_dossier.py`, `beaume/adapters/chercheur_articles_fts5.py` | Résoudre les références explicites et rechercher des candidats |
| Corpus | `beaume/adapters/depot_sqlite.py`, `beaume/legal/model.py` | Stocker et retrouver les articles et leurs versions |
| Génération | `beaume/application/prompts.py`, `schemas.py`, `beaume/adapters/generateur_ollama.py` | Fournir contexte et schéma au LLM local |
| Contrôle | `beaume/adapters/verificateur_standard.py` | Vérifier les citations selon les données du corpus |
| Restitution | `beaume/output/rapport.py` | Présenter résultats, rejets et avertissements |

`analyse_dossier.py` enrichit les candidats avec les références explicites
uniquement résolues au statut `UNIQUE`. Les mentions non résolues ne doivent pas
être transformées en articles confirmés. Le LLM sélectionne des identifiants
candidats ; les références et extraits sont reconstruits depuis le corpus.
Le pipeline transmet ensuite les citations au vérificateur.

## Les frontières importantes

- Le schéma JSON contraint la forme et certaines valeurs ; il ne prouve pas le sens.
- Les contrôles fichier/page ne prouvent pas le soutien factuel d’une affirmation.
- Le dépôt et le vérificateur ne peuvent contrôler que les versions disponibles.
- Une citation juridiquement pertinente nécessite plus que sa présence dans le corpus.
- Les adaptateurs vectoriels présents ne signifient pas que le script nominal
  utilise un moteur de recherche vectoriel : il compose actuellement FTS5.

## Données locales

`beaume/config/paths.py` définit les répertoires :

| Chemin relatif | Usage |
| --- | --- |
| `data/inbox/` | Pièces à analyser |
| `data/out/` | Rapports produits |
| `data/legal/` | Sources et ressources juridiques |
| `data/vector/` | Bases et index, dont `legi_full.sqlite` |
| `data/logs/`, `data/tmp/` | Journaux et fichiers temporaires |
| `data/training/` | Préparation des jeux d’entraînement par les scripts concernés |

Ces ressources ne sont pas livrées par un clone Git. Les noms `v2` ou `v3` de
bases expérimentales ne changent pas le chemin ouvert par le script nominal.

## Produit et laboratoire Balladeur

Beaume analyse les pièces. Le Balladeur explore la fabrication de données
synthétiques pour des tâches d’entraînement et d’évaluation distinctes.
Les lots locaux et les branches de recherche ont leurs propres versions et preuves.
La présence d’un script d’usine n’atteste pas qu’un dataset est prêt à entraîner
un modèle. Une structure cohérente et des contrôles déterministes ne suffisent
pas à valider les conclusions juridiques.

## Faire évoluer le code

Préserver les contrats dans `ports/` et les modèles dans `legal/`. Un changement
partagé exige de vérifier ses consommateurs. Séparer les fonctions de calcul
et de validation des accès disque, réseau et modèles. Garder les modifications
ciblées et documenter leur effet sur les données et les sorties.
Voir [le guide de contribution](../CONTRIBUTING.md).
