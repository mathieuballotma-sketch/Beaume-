# Beaume

**Prototype local d’assistance documentaire destiné aux avocats.**

[English overview](README.en.md)

[![Tests](https://github.com/mathieuballotma-sketch/Beaume-/actions/workflows/tests.yml/badge.svg)](https://github.com/mathieuballotma-sketch/Beaume-/actions/workflows/tests.yml)
[![Licence AGPL-3.0](https://img.shields.io/badge/licence-AGPL--3.0-blue)](LICENSE)

Beaume vise à aider l’avocat à lire un dossier, à en obtenir une synthèse et à retrouver les pièces qui l’étayent. Il vise aussi à **proposer les articles de loi susceptibles d’être liés aux faits et aux questions juridiques du dossier**, avec les références et les versions disponibles dans le corpus, pour que l’avocat puisse les examiner.

**Beaume assiste l’avocat ; il ne le remplace pas.** L’avocat conserve l’analyse juridique, vérifie les faits, les sources, la pertinence et l’applicabilité des textes, puis prend les décisions. Le dépôt contient un prototype et des expériences, **pas une application validée pour les dossiers de clients**.

## Ce qui est disponible

Le parcours principal publié sait extraire le texte de PDF textuels, découper et sélectionner des passages, rechercher des articles candidats dans un corpus local et appeler un modèle local via Ollama. Les références sélectionnées sont reconstruites à partir du corpus ; le programme contrôle notamment l’existence de l’article et de sa version à la date de référence, puis produit un rapport Markdown. Ces contrôles dépendent du corpus disponible : ils ne prouvent pas que l’article est pertinent ou applicable au dossier. La démonstration ci-dessous utilise une réponse fixe et des données fictives.

Le [laboratoire](laboratoire/README.md) contient des expériences distinctes du parcours principal : un prototype d’orchestration et d’OCR Apple, un adaptateur de génération utilisant `llama.cpp`, et des [sources Swift expérimentales](laboratoire/inference_swift_experimentale/README.md) pour certaines opérations d’inférence, dont un parcours propre à une configuration de 28 couches. Ces dernières ne forment pas un moteur prêt à l’emploi et ne fournissent pas ici de génération complète reproductible. Les conditions et limites figurent dans chaque dossier.

**Un passage localisé ne prouve pas qu’il étaye une affirmation.** Les contrôles et les tests ne démontrent ni l’exhaustivité du dossier, ni la fidélité générale d’un résumé, ni la pertinence juridique d’une référence. Le fonctionnement local ne garantit pas à lui seul la confidentialité.

## Essayer la démonstration

Python 3.11 ou plus récent est nécessaire ; Python 3.12 est recommandé. L’installation des dépendances nécessite une connexion. Une fois installées, la démonstration s’exécute sans réseau, sans modèle et sans corpus externe.

```sh
git clone https://github.com/mathieuballotma-sketch/Beaume-.git
cd Beaume-
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,corpus]'
PYTHONPATH=. python scripts/demo_hors_ligne.py
```

Le rapport est créé dans `data/out/demo_hors_ligne.md`. Pour un essai avec modèle, corpus et PDF textuels, voir le [guide de démarrage](docs/DEMARRAGE.md). Les poids des modèles et les corpus juridiques ne sont pas inclus.

Extrait de la démonstration, entièrement fictive :

```text
Contexte : DEMONSTRATION FICTIVE : dommage à un vélo fictif.
code_civil - Article 9999
Source dans le dossier : exemple.pdf (page 1)
Extrait cité : REGLE FICTIVE DE TEST : dommage au velo fictif.
```

Le libellé actuel du rapport « Articles applicables (verifies) » est trop
affirmatif : la vérification technique ne démontre pas l'applicabilité juridique.
Ce défaut de présentation reste à corriger avant un usage réel.

## Documentation

- [Fonctionnalités disponibles et limites](docs/ETAT_PROJET.md)
- [Architecture du dépôt](docs/ARCHITECTURE.md)
- [Tests et conditions de reproduction](docs/TESTS.md)
- [Laboratoire et expériences publiées](laboratoire/README.md)
- [Contribuer](CONTRIBUTING.md)

Projet porté par **Mathieu Bellot**, développeur indépendant et non avocat. Merci de ne pas joindre de dossiers clients aux issues ou aux jeux de tests.

## Licence

Le code est publié sous **GNU AGPL version 3 uniquement** : [LICENSE](LICENSE). Les modèles, corpus et contenus tiers gardent leurs propres conditions : [licences des données](docs/LICENCES_DONNEES.md).
