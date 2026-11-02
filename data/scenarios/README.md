# Exemples et gabarits de tests

Ces fichiers servent à vérifier les contrats logiciels de `beaume/scenario`.
Ils ne constituent ni un jeu d'entraînement validé, ni des actes utilisables.

## Contenu publié

- `exemples/` : un scénario de développement dont les identités, événements et
  arguments sont déclarés fictifs. La mention d'une décision comme inspiration
  ne constitue pas une preuve de ses valeurs ni une validation juridique.
- `structures/*.md` : quatre supports techniques rédigés pour ce dépôt le
  2 novembre 2026. Ils remplacent les anciens textes de gabarits dont l'origine
  n'était pas suffisamment documentée. Ils ne reproduisent pas un cours EFB
  ni un modèle d'acte fourni par un tiers.
- `structures/*.meta.json` : noms, types et caractère obligatoire des champs.
  Ces métadonnées décrivent les contraintes du programme, pas celles du droit.

Les noms historiques des fichiers sont conservés pour préserver les références
et les tests. Chaque nouveau texte porte un avertissement de test logiciel.
Les balises typées sont conservées ; les contenus et leurs empreintes changent.
Un rapport calculé avec les anciens gabarits doit être régénéré.

Les nouveaux textes techniques sont distribués sous la licence AGPL-3.0-only
du dépôt. Cette déclaration ne donne aucun droit sur les anciens supports ou
sur d'éventuelles sources externes.

## Sorties locales

`rapports/` est exclu de Git. Pour produire un rapport structurel local :

```sh
python scripts/valider_scenario.py data/scenarios/exemples/beaume-sc-licenciement-0002-v1.json
```

Le script refuse d'écraser un rapport existant. Un résultat structurel accepté
n'atteste ni la pertinence juridique, ni l'aptitude à entraîner un modèle.
