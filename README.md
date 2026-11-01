# Beaume

**Lire un dossier. Retrouver ses sources. Garder la maîtrise en local.**

[![Tests](https://github.com/mathieuballotma-sketch/Beaume-/actions/workflows/tests.yml/badge.svg)](https://github.com/mathieuballotma-sketch/Beaume-/actions/workflows/tests.yml)
[![Licence AGPL-3.0](https://img.shields.io/badge/licence-AGPL--3.0-blue)](LICENSE)

Beaume est un **prototype d’assistant juridique local pour avocats**. Il explore
la lecture de dossiers, l’extraction de faits traçables et la recherche de textes
de loi contrôlables. L’avocat conserve la vérification et la décision juridique.

> **Recherche et développement — non validé pour un usage professionnel.**
> Des tests logiciels réussis ne prouvent ni la pertinence juridique,
> ni l’exhaustivité d’une analyse, ni la confidentialité de toute configuration.

[Démarrage](docs/DEMARRAGE.md) · [Architecture](docs/ARCHITECTURE.md) ·
[État et limites](docs/ETAT_PROJET.md) · [Contribuer](CONTRIBUTING.md) ·
[Hugging Face](https://huggingface.co/Beaume/beaume-qwen-3b)

## Essayer sans télécharger de modèle ou de corpus

```sh
git clone https://github.com/mathieuballotma-sketch/Beaume-.git
cd Beaume-
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,corpus]'
PYTHONPATH=. python scripts/demo_hors_ligne.py
```

Le rapport est créé dans `data/out/demo_hors_ligne.md`. Cette démonstration
utilise un PDF fictif, un minuscule corpus fictif et une réponse fixe explicitement
étiquetée. Elle exerce lecture PDF, recherche, orchestration et vérification,
**sans évaluer un modèle ni représenter du droit réel**. Aucun appel réseau
n’est nécessaire à son exécution après installation des dépendances.

Pour utiliser un modèle local et un corpus juridique, suivre le
[guide complet](docs/DEMARRAGE.md). Les corpus et poids ne sont pas inclus dans le clone.

## Ce que contient le code

- Lecture de PDF textuels et découpage avec fichier et page.
- Recherche SQLite FTS5 et résolution de références explicites.
- Génération structurée via Ollama.
- Vérification des citations et des versions selon le corpus et la date fournis.
- Rapport Markdown avec avertissements et rejets.
- Contrats expérimentaux de scénarios synthétiques, validation et tests associés.

Une mention dans une pièce ne prouve pas l’applicabilité d’un article ; une page
existante ne prouve pas qu’elle soutient l’affirmation. Le pipeline nominal
n’effectue pas l’OCR des PDF scannés. Voir [les limites](docs/ETAT_PROJET.md).

## Qualité et mesures

La CI exécute les tests sur Python 3.11 et 3.12, vérifie les fichiers publiés et
lance la démonstration autonome. Les tests exigeant un gros corpus local sont
explicitement ignorés lorsqu’il est absent. Le badge montre l’état du workflow,
pas une certification juridique. [Périmètre des tests](docs/TESTS.md).

Les résultats historiques de recherche portent sur un jeu très petit et des
annotations provisoires : ils ne démontrent pas une fiabilité générale.
[Résultats et méthode](docs/AUDIT_RECHERCHE.md).

## Données et confidentialité

L’analyse est conçue pour Ollama exécuté localement. Les téléchargements de
modèles et corpus sont distincts du traitement des pièces. La configuration
réseau réelle doit être contrôlée avant tout usage sensible.

Groq a servi ponctuellement à préparer des exemples à partir de sources publiques ;
il n’est pas requis par le pipeline d’analyse. Son support optionnel appartient
à un script de préparation. Aucun dossier client ne doit être partagé dans les
issues ou intégré aux jeux d’entraînement.

## Participer

Projet porté par **Mathieu Bellot, développeur indépendant et non avocat**.
Nous recherchons des retours sur les besoins des cabinets, la traçabilité et
les cas d’échec reproductibles, avec des exemples publics ou synthétiques.

[Signaler un problème](https://github.com/mathieuballotma-sketch/Beaume-/issues/new/choose)
· [Guide de contribution](CONTRIBUTING.md) · [Documentation](docs/README.md)

## Licence

Le code Beaume est publié sous **GNU AGPL version 3 uniquement (AGPL-3.0-only)**.
Voir [LICENSE](LICENSE). L’usage commercial est permis sous les conditions de
cette licence, notamment ses obligations relatives au code source et aux versions
modifiées utilisées à travers un réseau. Les corpus, modèles et contenus tiers
conservent leurs propres conditions : [provenance et licences](docs/LICENCES_DONNEES.md).
