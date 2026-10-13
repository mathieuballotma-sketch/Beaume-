# Décisions techniques — Beaume

## 2026-10-08 — Arborescence
- Code dans `beaume/`, données dans `data/`.
- Chemins centralisés dans `beaume/config/paths.py`.
- Aucune donnée client dans git.

## 2026-10-08 — Logging
- Logger rotatif, 5 Mo × 5 fichiers, dans `data/logs/`.

## 2026-10-08 — Les 6 lois d'architecture
1. Dépendance descendante (couches L0->L5, jamais l'inverse)
2. Conservation de l'information (chaque transformation traçable)
3. Tiers exclu (machine à états fermée)
4. Inversion des dépendances (ports & adapters)
5. Composition fermée (une porte d'entrée par module)
6. Pureté au cœur, effets aux bords

## 2026-10-08 — Ontologie juridique
- Identifiant = LEGIARTI/LEGITEXT/JURITEXT + 12 chiffres
- Numéro humain (L. 1234-1) = alias, jamais identifiant
- Un article = plusieurs versions datées
- Une citation porte TOUJOURS une date de référence
- Immutabilité (frozen=True) sur les versions

## 2026-10-08 — Ports
- `Extracteur` : contrat unique pour tous les formats
- `RegistreExtracteurs` : ajout sans modification
- Aucun `if suffix == ".pdf"` dans le pipeline

## 2026-10-08 — Machine à états
- États : DEPOSE -> EXTRAIT -> DECOUPE -> INDEXE -> ANALYSE -> VERIFIE -> PUBLIE
- ECHEC accessible depuis n'importe quel état non terminal
- Transitions illégales = exception levée
- Historique horodaté conservé

## 2026-10-13 — HUD comme assistant, pas comme application
- L'avocat dépose son dossier dans la fenêtre HUD.
- Dès que l'analyse démarre, la fenêtre se replie dans un coin de l'écran.
- À chaque étape, le texte affiché décrit précisément ce que Beaume fait
  (ex : « Recherche des articles applicables… »).
- Signal discret : un point s'affiche au démarrage d'une action. Pas
  d'animation coûteuse en CPU/GPU.
- Objectif : habituer l'avocat à une **présence d'assistance**, pas à
  l'ouverture d'une application.
- Conséquence technique : le pipeline doit émettre des événements
  d'étape vers le HUD (aujourd'hui, il log dans un fichier). À prévoir
  une fois le noyau fiable.

## 2026-10-13 — Priorité fiabilité, puis vitesse
- Objectif : Beaume rend un résumé fiable d'un dossier client, avec
  articles cités, liens Legifrance et preuves vérifiables.
- **Fiabilité d'abord** : on ne cherche pas à être rapide tant que le
  taux de réussite n'est pas mesuré et acceptable.
- **Vitesse ensuite** : une fois la fiabilité mesurée, on optimise le
  temps là où il se perd réellement (mesure avant optimisation).
- Une analyse peut prendre plusieurs minutes si l'avocat voit ce qui se
  passe et comprend pourquoi. Un outil rapide mais faux est inutilisable.
- Conséquence : on ne peut pas dire « Beaume est fiable » sans un jeu
  de test et un chiffre. Le harnais de mesure est le prérequis de toute
  décision d'optimisation.
