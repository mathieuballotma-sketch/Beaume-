# Laboratoire Beaume

Ce laboratoire rassemble des expériences séparées du parcours public de Beaume. Leur objectif est de comprendre les erreurs et de tester des solutions avant intégration. Elles ne démontrent ni une fiabilité générale ni une validation juridique ou professionnelle. Les données retenues ici sont fictives ; ne pas utiliser de dossiers clients.

## S'y retrouver

- [Historique des expériences et décisions](HISTORIQUE.md) : problème, approche, observations et limites.
- [Protocole d'évaluation et prochaines étapes](EVALUATION.md) : mesures et conditions de comparaison.
- [Signalement exploratoire v3](signalement_v3/) : détecteur déterministe et cas synthétiques ; ce n'est pas une validation sémantique.
- [Calcul de référence](calcul_reference/) : attention causale pédagogique en Python ; ce n'est pas un moteur d'inférence complet.

Cette première publication est une **sélection**, pas une archive exhaustive des travaux historiques. Les scripts et résultats conservés dans les laboratoires locaux ne sont pas tous publiés ni forcément reproductibles depuis ce dépôt. Des références aux expériences non incluses sont signalées comme telles dans l'historique. Aucune donnée cliente, aucun poids de modèle ni corpus juridique réel ne sont inclus.

## Rejouer les briques incluses

Avec Python 3.11 ou plus récent :

```sh
cd laboratoire/signalement_v3
python3 brique_signalement_v3.py --registre reference --out /tmp/beaume_signalement.json
```

La commande refuse d'écraser un résultat déjà présent : choisir un autre nom si nécessaire. Les 22 cas synthétiques de référence ont été relancés sur la copie préparée le 14 novembre 2026 : 22 conformes aux attentes. Cela ne démontre pas la qualité sur d'autres dossiers.

Pour l'attention de référence, installer `pytest` dans un environnement de développement puis :

```sh
cd laboratoire/calcul_reference
python3 -m pytest -q -p no:cacheprovider test_moteur_reference.py
```

Six tests ont réussi sur la copie préparée. Ils portent sur des vecteurs déjà fournis : aucun modèle n'est chargé ni exécuté.

## Statuts à distinguer

Une page identifiée, un passage retrouvé et un passage qui étaye une affirmation sont des constats distincts. Une alerte est une invitation à examiner, pas la preuve d'une contradiction. Un résultat issu d'une relecture par IA n'est pas une annotation humaine indépendante. La localisation de texte n'établit pas l'exhaustivité du dossier.
