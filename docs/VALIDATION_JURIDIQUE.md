# Protocole de validation juridique — préparation

Date : 21 octobre 2026. **Protocole proposé, aucune revue réalisée dans cette session.**
Beaume reste un prototype ; sa pertinence juridique n'est pas démontrée.

## 1. Périmètre et personnes

Commencer sur un domaine étroit, par exemple le licenciement économique,
avec un avocat compétent dans ce domaine. Consigner son rôle, la date de revue
et les limites de sa mission. Sans relecteur disponible, garder les annotations
au statut provisoire. Un LLM juge est un filtre, pas une validation juridique.

Préparer un pilote de 20 cas publics ou synthétiques diversifiés : cas simples,
informations manquantes, plusieurs articles pertinents, dates ambiguës,
exceptions et aucun article pertinent dans les candidats. Ce nombre permet
d'identifier des défauts ; il ne certifie pas la fiabilité du produit.
Vérifier les conditions de réutilisation et les données personnelles résiduelles.
Aucun document client dans les jeux d'entraînement ou les services externes.

## 2. Séparer développement et test final

Le pilote sert au développement et à l'affinement du guide d'annotation.
Constituer ensuite un test final indépendant, dont la taille et les critères
de réussite sont fixés avant de regarder les résultats du modèle.
Exclure de l'entraînement et des prompts de génération les cas de ce test.
Regrouper décisions, faits dérivés, doublons et paraphrases dans une seule
partition. Un split par numéro d'article ne suffit pas à empêcher les fuites.

Si l'on règle le système après lecture du test final, le traiter comme un jeu
de développement et constituer un nouveau test indépendant pour la conclusion.

## 3. Fiche d'annotation pour chaque cas

- Identifiant stable, origine publique/synthétique, empreinte de source,
  groupe de décision/paraphrases et partition.
- Faits déterminants et preuves exactes (document, page ou offsets).
- Dates pertinentes et leur rôle ; informations manquantes ou incertaines.
- Pour chaque référence : code, numéro, identifiant de version LEGIARTI,
  famille si disponible, intervalle de validité et lien de source officiel.
- Pertinence : nécessaire / utile / non pertinent / indéterminé, avec justification.
- Cas sans réponse et informations supplémentaires nécessaires pour conclure.
- Auteur de l'annotation, date, statut provisoire/relu/contesté et arbitrage.

Préparer les références sans voir la réponse du modèle lorsque possible pour
limiter l'ancrage. Un visa d'arrêt n'est pas automatiquement une réponse attendue.
Une référence absente des annotations n'est pas automatiquement un négatif.
Toute référence nouvelle proposée par le moteur doit être revue avant de la
compter comme erreur. Conserver les désaccords ; une seconde revue ciblée est
souhaitable sur les cas ambigus. Signaler si un seul relecteur a participé.

## 4. Mesurer séparément les étapes

Fixer corpus (empreinte), code (commit et diff), modèle, configuration, cas et
annotations. Conserver candidats et rangs, choix du LLM, motifs de rejet et
résultat final. Comparer les moteurs sur les mêmes entrées et le même corpus.

- Recherche : Recall@5 et @10 sur les références attendues annotées ; publier
  les résultats par cas et agrégés avec numérateurs et dénominateurs.
- Précision : résultats jugés pertinents / résultats jugés ; publier aussi la
  couverture des jugements et les références encore indéterminées.
- Résumé : faits fidèles, inventions, omissions déterminantes et preuves qui
  étayent réellement l'affirmation ; fichier/page existants ne suffisent pas.
- Citations : identité, texte exact, version à la date pertinente, pertinence
  et provenance documentaire sont des contrôles distincts.
- Abstention : bonnes abstentions et abstentions excessives, séparées selon
  qu'il existe une réponse dans le corpus ou seulement dans les candidats.
- Technique : erreurs d'exécution, JSON invalide, latence et mémoire.

Les cas sans positif annoté n'ont pas de Recall défini : les rapporter séparément.
Publier les cas contestés et leur impact ; ne pas les supprimer pour améliorer
le score. Rapporter la taille du jeu, sa diversité et l'incertitude des mesures.

## 5. Décision et publication

Définir avec le relecteur les erreurs critiques, les seuils acceptables et la
conduite à tenir si un seuil est manqué, avant l'évaluation finale. Ne pas
inventer de seuil de fiabilité juridique à partir des scores du pilote.

Le rapport indique : ce qui a été exécuté, ce qui a été relu, les erreurs,
les limites et le périmètre exact des conclusions. Tests logiciels, conformité
JSON et revue juridique sont complémentaires. Aucun score seul n'autorise à
annoncer que Beaume est fiable pour tous les dossiers ou prêt pour la production.
