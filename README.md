# Beaume

**Comprendre un dossier. Retrouver ses sources. Construire avec l’avocat.**

[![Tests](https://github.com/mathieuballotma-sketch/Beaume-/actions/workflows/tests.yml/badge.svg)](https://github.com/mathieuballotma-sketch/Beaume-/actions/workflows/tests.yml)
[![Licence AGPL-3.0](https://img.shields.io/badge/licence-AGPL--3.0-blue)](LICENSE)

## Beaume, en quelques mots

Beaume est un projet d’assistant documentaire local destiné aux avocats. Son ambition est de les aider à prendre connaissance d’un dossier, à retrouver les informations importantes et à passer naturellement d’une synthèse aux documents qui la nourrissent.

Un dossier peut contenir de nombreuses pièces : les parcourir, retrouver une date ou replacer une information dans son contexte prend du temps. Beaume cherche à rendre ce travail plus lisible et vérifiable, pour laisser davantage de place à l’analyse du professionnel.

**L’avocat reste au centre : il vérifie les sources, exerce son jugement et prend les décisions.** Beaume est en recherche et développement ; il n’est pas validé pour un usage professionnel.

## Une philosophie : construire, relier, vérifier

Beaume se développe progressivement, à partir d’un premier outil utile et de briques capables d’évoluer ensemble. Chaque brique doit avoir un rôle clair, des entrées et sorties identifiables et des liens compréhensibles avec les autres. Avant d’ajouter une fonction, le projet cherche à comprendre ce qu’elle apporte, où elle s’insère et comment vérifier son comportement.

Cette approche s’inspire de systèmes vivants et de la manière dont des fonctions spécialisées coopèrent. Les noms de « fourmis », « reines » ou « Lucy » désignent des idées d’organisation, de coordination et de mémoire dans la vision à long terme. **Ils ne signifient pas que ces éléments sont déjà opérationnels.**

L’intelligence artificielle est une capacité parmi d’autres : elle peut aider à comprendre ou à rédiger, tandis que des contrôles logiciels vérifient ce qui peut l’être. Une information manquante, ambiguë ou contradictoire doit rester visible. Un passage localisé ne prouve pas à lui seul qu’il étaye une affirmation.

Le projet privilégie une utilisation locale et la maîtrise des documents par leur propriétaire. Les permissions, les flux réseau et la confidentialité devront être vérifiés dans chaque configuration : le fonctionnement local ne suffit pas à lui seul à garantir la sécurité.

## Ce que la première version cherche à permettre

Le premier objectif est précis : **aider un avocat à lire un dossier et à vérifier un résumé à partir des pièces d’origine**.

1. L’avocat choisit un dossier et fournit quelques PDF textuels pris en charge.
2. Beaume lit les pièces et prépare un résumé clair et structuré.
3. L’avocat sélectionne une information du résumé.
4. Beaume propose le ou les documents et passages associés, avec la page lorsque disponible.
5. L’avocat ouvre la source pour la consulter et revient au résumé sans perdre le fil.
6. Si une source manque, reste ambiguë ou appelle une vérification, Beaume le signale au lieu de donner une certitude artificielle.

Ce parcours constitue **la cible de développement** : il n’est pas encore intégré et validé de bout en bout. Les premiers essais porteront sur un périmètre limité de documents. La prise en charge des scans, d’autres formats et spécialités viendra selon les besoins et les résultats observés.

## Où en est Beaume aujourd’hui ?

Le dépôt public contient un prototype avec lecture de PDF textuels, recherche dans un corpus, génération structurée avec Ollama, contrôles de références et production d’un rapport Markdown. Une démonstration autonome permet d’exercer une partie de la chaîne sur des données fictives.

En parallèle, le laboratoire explore des éléments pour la suite : le **Balladeur** produit et examine des dossiers synthétiques pour développer et tester le système ; des prototypes étudient la proposition de plusieurs sources et l’ouverture de pages PDF. Ces travaux ne sont pas tous intégrés au dépôt public. Ils ne prouvent ni la fiabilité générale du résumé ni la validité juridique des résultats.

La prochaine étape est de relier progressivement les briques nécessaires au premier parcours : résumé, informations, sources, états d’incertitude et navigation. Il faudra ensuite tester la qualité des réponses, les cas d’échec et les ressources utilisées par ordinateur. [Voir l’état et les limites](docs/ETAT_PROJET.md).

## La suite : confronter Beaume au terrain en 2027

L’objectif est de se rapprocher d’avocats **durant l’année 2027** pour comprendre leurs méthodes, leur présenter une première expérience et recueillir leurs retours sur son utilité, sa lisibilité et la vérification des sources.

Les premiers échanges pourront s’appuyer sur des dossiers fictifs ou publics adaptés. L’utilisation éventuelle de documents professionnels demandera au préalable un cadre et des autorisations appropriés. La confrontation au terrain guidera les corrections et les priorités ; elle ne constitue pas une validation acquise ni une promesse de date de livraison.

[Feuille de route](docs/ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md) · [État et limites](docs/ETAT_PROJET.md)

## Essayer la démonstration hors ligne

La démonstration actuelle utilise un PDF fictif, un petit corpus fictif et une réponse fixe. Elle ne mesure pas la qualité d’un modèle et ne représente pas une analyse juridique réelle. Après installation des dépendances, son exécution ne nécessite pas d’appel réseau.

```sh
git clone https://github.com/mathieuballotma-sketch/Beaume-.git
cd Beaume-
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,corpus]'
PYTHONPATH=. python scripts/demo_hors_ligne.py
```

Le rapport est créé dans `data/out/demo_hors_ligne.md`. Pour utiliser un modèle local et un corpus juridique, voir le [guide de démarrage](docs/DEMARRAGE.md). Les corpus et poids ne sont pas inclus dans le clone. L’OCR des scans n’est pas intégré au parcours nominal.

## Qualité, données et collaboration

Les tests automatisés vérifient des comportements logiciels sur leur périmètre ; ils ne certifient pas la pertinence juridique ou la généralisation. Voir le [périmètre des tests](docs/TESTS.md) et les [mesures de recherche](docs/AUDIT_RECHERCHE.md).

Projet porté par **Mathieu Bellot, développeur indépendant et non avocat**. Les retours sur les besoins des cabinets, les limites et les cas d’échec sont les bienvenus, avec des exemples publics ou synthétiques. Aucun dossier client ne doit être partagé dans les issues ni intégré aux jeux d’entraînement.

[Documentation](docs/README.md) · [Contribuer](CONTRIBUTING.md) · [Signaler un problème](https://github.com/mathieuballotma-sketch/Beaume-/issues/new/choose) · [Hugging Face](https://huggingface.co/Beaume/beaume-qwen-3b)

## Licence

Le code est publié sous **GNU AGPL version 3 uniquement (AGPL-3.0-only)** : [LICENSE](LICENSE). Les corpus, modèles et contenus tiers conservent leurs propres conditions : [provenance et licences](docs/LICENCES_DONNEES.md).
