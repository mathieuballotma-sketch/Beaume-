# Tests et intégration continue

## Reproduire les tests

```sh
python -m pip install -e '.[dev,corpus]'
python -m pytest -q -rs -p no:cacheprovider
python scripts/verifier_publication.py
PYTHONPATH=. python scripts/demo_hors_ligne.py --sortie /tmp/beaume-demo.md
```

Le workflow [Tests](../.github/workflows/tests.yml) s’exécute sur push,
pull request et déclenchement manuel, avec Python 3.11 et 3.12 sur Ubuntu.
Les téléchargements de données Hugging Face sont désactivés pendant les tests.
L’installation des dépendances nécessite Internet. Aucun serveur Ollama ni
modèle n’est requis pour la suite automatisée nominale.

## Mesure locale du 1 novembre 2026

Sur le code préparé pour cette publication, sous macOS avec Python 3.12 :
**669 tests réussis, 33 ignorés**. Cette mesure a utilisé l’environnement Python
existant du développeur ; le workflow doit confirmer le résultat sur une
installation Linux neuve. Le badge du README montre son statut réel.

Les tests ignorés nécessitent des données locales ou des conditions spécifiques ;
`-rs` affiche chaque motif. Ne pas les compter comme réussis. La suite n’est pas
un benchmark de pertinence ni une validation juridique.

La démonstration autonome vérifie le parcours PDF → recherche → réponse fixe →
contrôle → rapport avec des données fictives. Elle ne mesure ni un LLM, ni un
corpus réel. Elle refuse d’écraser une sortie existante.

## Publication

`verifier_publication.py` inspecte les fichiers suivis pour détecter des catégories
de documents internes, artefacts locaux et chemins personnels. C’est un garde-fou
limité, pas un détecteur exhaustif de secrets. Inspecter le diff avant publication.
