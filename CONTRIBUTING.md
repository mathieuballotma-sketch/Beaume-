# Contribuer à Beaume

Merci de contribuer à un prototype dont la fiabilité doit être démontrée.
Les retours métier et les contre-exemples reproductibles sont aussi utiles
que les contributions de code.

## Proposer un retour métier

Décrire la tâche, la difficulté actuelle, le résultat utile et la manière de
le vérifier. Utiliser un exemple fictif ou public dont le partage est autorisé.
Ne pas joindre de dossier client, d’identité sensible, de clé API ou de journal
contenant des pièces. Une décision publique peut encore contenir des données
personnelles : vérifier ce que l’on partage.

## Signaler un problème

Créer une [issue](https://github.com/mathieuballotma-sketch/Beaume-/issues) avec :

- version ou commit, système, Python et modèle utilisés ;
- commande minimale, corpus et configuration pertinents, sans secret ;
- résultat attendu, résultat observé et moyen de reproduction ;
- statut de l’exemple : public, synthétique ou non partageable.

Pour une vulnérabilité, ne pas publier de données exploitables ou confidentielles
sur une issue publique. Utiliser le signalement privé GitHub s’il est disponible ;
sinon demander un canal privé sans divulguer le détail sensible.

## Proposer du code

1. Lire [l’architecture](docs/ARCHITECTURE.md) et les contrats concernés.
2. Travailler sur une branche avec un périmètre limité ; préserver les données
   locales et les modifications préexistantes.
3. Ajouter une reproduction ou des tests adaptés aux comportements modifiés.
4. Exécuter les vérifications pertinentes et rapporter ce qui n’a pas été exécuté.
5. Décrire les effets sur les schémas, sorties, identifiants, corpus et anciens lots.

Ne pas réduire un contrôle pour faire passer un exemple. Une référence ambiguë
ou une preuve absente doit rester visible. Ne pas présenter une sortie de LLM
comme une annotation humaine validée. Ne pas publier de corpus volumineux,
modèles ou données d’entraînement sans vérifier provenance et droits.

La licence du code reste à définir. Aucune licence de contribution supplémentaire
n’est créée par ce document ; clarifier les droits avant une contribution substantielle.
