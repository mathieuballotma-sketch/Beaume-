# Beaume

**Prototype local d’assistance documentaire destiné aux avocats.**

[![Tests](https://github.com/mathieuballotma-sketch/Beaume-/actions/workflows/tests.yml/badge.svg)](https://github.com/mathieuballotma-sketch/Beaume-/actions/workflows/tests.yml)
[![Licence AGPL-3.0](https://img.shields.io/badge/licence-AGPL--3.0-blue)](LICENSE)

Beaume explore la lecture de dossiers et la recherche de références afin d’aider un professionnel à retrouver les informations et à vérifier leurs sources. Le dépôt contient un prototype et des expériences, **pas une application validée pour les dossiers de clients**. La vérification et la décision juridique restent à la charge du professionnel.

## Ce qui est disponible

Le parcours principal publié sait extraire le texte de PDF textuels, découper et sélectionner des passages, rechercher dans un corpus local, appeler un modèle local via Ollama, contrôler certaines références et produire un rapport Markdown. La démonstration ci-dessous utilise une réponse fixe et des données fictives.

Le [laboratoire](laboratoire/README.md) contient aussi des briques expérimentales distinctes du parcours principal, notamment un prototype d’orchestration et de lecture avec OCR Apple, ainsi que des premiers calculs matriciels. Les conditions et limites des essais sont indiquées dans chaque dossier. Ces briques ne constituent pas un moteur d’inférence autonome : le prototype de génération fait appel à `llama.cpp`.

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

## Documentation

- [Fonctionnalités disponibles et limites](docs/ETAT_PROJET.md)
- [Architecture du dépôt](docs/ARCHITECTURE.md)
- [Tests et conditions de reproduction](docs/TESTS.md)
- [Laboratoire et expériences publiées](laboratoire/README.md)
- [Contribuer](CONTRIBUTING.md)

Projet porté par **Mathieu Bellot**, développeur indépendant et non avocat. Merci de ne pas joindre de dossiers clients aux issues ou aux jeux de tests.

## Licence

Le code est publié sous **GNU AGPL version 3 uniquement** : [LICENSE](LICENSE). Les modèles, corpus et contenus tiers gardent leurs propres conditions : [licences des données](docs/LICENCES_DONNEES.md).
