# Scripts expérimentaux

Ce répertoire est distinct du pipeline d'analyse documenté dans le README.

## `usine_historique.py`

Ancien prototype de génération de dossiers. **La génération est désactivée.**
Les gabarits qu'il contient ont des constantes propres à une affaire publique ;
ils sont conservés comme contre-exemples pour les tests du blocage, pas comme
sources d'entraînement ou modèles de documents.

Le module conserve les contrôles de montants décimaux, de dates candidates et
la commande `--marquer-inelegibles`, qui produit un manifeste local pour les
anciens dossiers sans les supprimer. Les chemins restent relatifs à la racine
du dépôt. L'entrée `scripts/11_usine_a_dossiers.py` reste disponible pour les
anciennes commandes et délègue à ce module.

Tests : `tests/unit/test_usine_fail_closed.py`. Retirer le blocage ne suffit pas
à rendre cette expérience utilisable : il faut un contrat de scénario, des
preuves et une évaluation appropriée. Le laboratoire Balladeur actif n'est pas
représenté par ce prototype historique.
