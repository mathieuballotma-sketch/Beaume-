# Audit de la recherche juridique

**Date : 2026-10-18**  
**État scientifique : non démontré.** Le pipeline de recherche est exécutable et
le code passe ses tests, mais le jeu de référence actuel est trop petit et n'a
pas été validé par un juriste. Les scores ci-dessous décrivent uniquement les
expériences précises indiquées.

> **Mise à jour du 2026-10-19 :** le code a depuis été refondu pour faire
> sélectionner un `article_id` parmi les candidats, hydrater les métadonnées et
> l'extrait depuis SQLite, borner la liste de candidats et renforcer les
> diagnostics. Les mesures d'inférence et les scores chiffrés ci-dessous sont
> historiques : ils n'ont pas été rejoués sur ce nouvel état, car Ollama local
> n'était pas accessible pendant cette vérification. La suite logicielle
> actuelle a, elle, été relancée : 319 tests passent et 2 sont ignorés.

## Défauts confirmés et corrections dans le code

- `scripts/bench_recherche.py` mesurait auparavant une auto-recherche : les mots
  de l'article attendu servaient eux-mêmes de requête. Ses anciens Recall@K ne
  mesuraient donc pas la recherche de loi à partir de faits. Ce mode reste
  disponible sous le nom `self_retrieval`, étiqueté comme diagnostic d'index.
- Le benchmark de recherche utilise maintenant les requêtes factuelles de
  `beaume/bench/dossiers_test.json` et rapporte Recall@K, macro-recall, taux de
  requêtes avec un résultat pertinent et MRR. Il ne calcule pas de précision,
  car `must_cite` est une liste positive non exhaustive.
- `scripts/construire_dataset_entrainement.py` associait auparavant une
  référence à une loi à partir du seul numéro d'article. Un même numéro peut
  exister dans plusieurs codes ; le script pouvait donc créer une paire avec
  le mauvais texte. Il conserve maintenant code, numéro et dates de version,
  utilise la date des faits et écarte les références non résolues ou ambiguës.
- `scripts/verifier_dataset.py` contrôle maintenant le contrat de sortie fondé
  sur `article_id`, sa présence parmi les candidats, le fichier, les pages et
  la cohérence avec le manifeste. Il ne valide pas la pertinence juridique.
  Les anciennes données à base de `code/numero/extrait` ne suivent pas ce
  contrat et doivent être régénérées ou auditées avec leur ancien outil.
- `scripts/generer_dataset_ft.py` garde les données automatiques au statut
  `genere_auto_a_revoir`, écrit séparément les exemples embedder et LLM, protège
  les sorties existantes et trace les IDs candidats. Les exemples juridiques
  dont la cible est masquée sont isolés dans `train_llm_sans_candidat_a_revoir_v2.jsonl`;
  leur label vide n'est pas validé et ils ne doivent pas entrer dans le train
  sans revue des candidats. Les leurres des positifs ne sont pas des négatifs
  juridiquement confirmés. Les exemples hors domaine n'évaluent pas
  l'abstention sur un cas juridique ambigu.
- Le vérificateur ne rejette plus automatiquement une version historique
  uniquement parce que son état source est `ABROGE` : la période de validité
  doit couvrir la date de référence. Un statut `INCONNU`, ou une version
  `ABROGE` sans date de fin, ne peut pas être déclarée valide. LEGI conserve
  bien les versions modifiées ou abrogées dans son fonds, et Légifrance permet
  de consulter une version à une date donnée ([documentation LEGI](https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides),
  [ChronoLégi](https://www.legifrance.gouv.fr/contenu/menu/cas-d-usage)).
- Le benchmark ouvre le corpus en lecture seule. `scripts/telecharger_corpus_v2.py`
  était une copie du modèle `Analyse` et terminait sans construire de corpus ;
  il échoue maintenant explicitement tant que l'intégration d'AgentPublic/legi
  n'est pas implémentée et validée.

## Mesures exécutées

### Recherche FTS5 sur le corpus local

Commande :

```bash
.venv/bin/python scripts/bench_recherche.py --sortie /tmp/beaume_bench_recherche.json
```

Résultat observé avec `legi_full.sqlite` : 5 requêtes synthétiques, 6 références
`must_cite`, FTS5 OR/BM25, MRR 0,600 ; Recall@1 micro 33,3 % (macro 40 %),
Recall@5 66,7 % (macro 80 %), Recall@10 66,7 % (macro 80 %). Le taux de requêtes
avec au moins une référence retrouvée est respectivement 40 %, 80 % et 80 %.

Les annotations sont marquées provisoires et non validées par un juriste. Ce
résultat est un diagnostic reproductible sur cinq exemples, pas une preuve de
pertinence juridique ni une comparaison de modèles.

### Pipeline complet avec Qwen 2.5 7B local

Commande :

```bash
.venv/bin/python scripts/bench_qualite.py --sortie /tmp/beaume_bench_qualite.json
```

Résultat observé sur les mêmes 5 dossiers : 0 erreur d'exécution, 4/6
références `must_cite` retrouvées (rappel micro 66,7 %, macro 80 %), 4/5
dossiers avec au moins une référence et 4/5 avec toutes leurs références
attendues. Le dossier `BE-LECO-002` avait deux références attendues et aucune
n'a été retrouvée ; les quatre autres dossiers ont chacun leur référence
attendue. Aucune citation n'a été rejetée par le vérificateur. La génération
Qwen 2.5 7B a pris en moyenne 29,3 secondes par dossier sur cette machine.

Le retrieval seul et le pipeline complet obtiennent ici le même rappel
`must_cite`@5 (4/6). Sur ce petit jeu, le dossier manqué est déjà absent des
10 premiers résultats lexicaux : le modèle génératif n'explique donc pas cet
échec observé. Cela n'identifie pas la cause juridique du classement. Le
nombre « zéro citation hors `must_cite` » n'est pas une mesure de précision,
car les annotations ne sont pas exhaustives.

### Dataset LLM présent sur le disque

L'audit historique de `data/entrainement/train_llm.jsonl` a lu 50 lignes :

- 50/50 réponses contiennent le champ `statut`, hors schéma de sortie du modèle ;
- chaque prompt contient 5 candidats et chaque réponse une citation ;
- les 50 lignes portent `genere_auto_filtre`, statut qui n'est pas une preuve
  de validation ;
- aucun manifeste n'est présent pour relier les lignes à leur source, date,
  graine ou modèle ;
- aucune validation par un juriste n'est documentée.

Le script retourne donc une erreur structurelle pour les 50 lignes. Il ne juge
pas leur pertinence juridique. Ce dataset ne doit pas être considéré comme
prêt pour un fine-tuning du schéma actuel.

### Dry-run du constructeur de paires embedder

Sans écrire ni remplacer de fichier, le constructeur corrigé a été exécuté sur
les 652 faits de `faits_clients_propres.jsonl` et le corpus v1 : 1 045 paires
résolues ; 227 références non résolues, dont 93 numéros absents du corpus et
134 sans version applicable à la date du fait. Aucune référence ambiguë ni
date invalide n'a été trouvée dans cet échantillon.

Ces références non résolues ne sont pas des négatifs : le corpus v1 ne conserve
qu'une version par article et ne suffit pas à reconstituer l'historique. Le
constructeur n'a pas réécrit les Parquet présents. Il faut réexaminer le
corpus historique avant de régénérer et d'entraîner.

Le split existant sépare bien les `id_fait` entre train et test (0 fait partagé
sur les fichiers inspectés). Il partage toutefois 29 numéros d'article entre
les deux côtés. Il évalue donc des faits nouveaux associés à des articles déjà
vus, et non la généralisation à des articles absents du train. Ce sont deux
questions d'évaluation différentes ; le rapport de test doit indiquer laquelle
il mesure.

### Corpus de lois

Le corpus v1 contient 25 767 articles et 25 767 versions ; les versions
présentes sont toutes au statut `en_vigueur`. Il ne permet donc pas de vérifier
les formulations historiques applicables aux dates anciennes des faits.
`data/vector/legi_full_v2.sqlite` existe, mais ne contient actuellement qu'une
table `versions` vide (0 ligne) ; ce n'est pas un corpus utilisable par le
pipeline.

## Ce qui reste non démontré ou bloqué

- Les cinq dossiers de recherche n'ont pas de références exhaustives
  indépendamment vérifiées. Recall@K peut sous-estimer les bons résultats non
  annotés et ne renseigne pas sur les citations erronées.
- Les faits automatiques associés à leur article source ne prouvent pas que
  cet article est juridiquement applicable aux faits inventés. Un autre LLM
  juge peut aider au tri, mais ne constitue pas une validation indépendante.
- Le benchmark de bout en bout a été exécuté avec Qwen 2.5 7B sur cinq dossiers
  synthétiques. Il n'y a pas d'évaluation sur des dossiers clients, et cinq
  exemples non revus ne démontrent ni la fiabilité ni l'absence d'hallucination
  en usage réel.
- La base v2 issue d'AgentPublic/legi n'est pas intégrée. Le fichier
  `data/vector/legi_full_v2.sqlite` ne constitue pas une base validée ; le
  script de génération s'arrête désormais clairement au lieu de simuler une
  réussite.
- Les anciens scores issus du self-retrieval ne doivent pas être présentés
  comme Recall@K sur des faits.

## Protocole nécessaire avant de revendiquer une validation

1. Constituer un jeu public de faits issus de décisions distinctes et annoter
   les articles réellement pertinents, en distinguant les citations de
   procédure, les moyens des parties et les motifs retenus par la juridiction.
2. Garder une provenance par exemple : décision, dates, article dans la version
   applicable, méthode d'annotation et état de revue. Un LLM juge reste un
   signal de triage.
3. Geler le jeu de test avant de modifier les prompts, le corpus ou le modèle.
   Grouper par décision/fait pour empêcher les paraphrases d'une même affaire
   de traverser les partitions.
4. Comparer sur les mêmes requêtes FTS5, embedder non entraîné, embedder
   entraîné et méthode hybride. Rapporter Recall@5/10, MRR, couverture et taux
   d'abstention ; calculer précision seulement si les références sont
   exhaustives.
5. Séparer l'évaluation du retrieval de celle du pipeline complet : validité
   des citations, provenance fichier/page, version temporelle, erreurs
   d'extraction et abstention.
6. Publier le nombre d'exemples, les intervalles d'incertitude et les versions
   des données/modèles. Tant qu'aucun professionnel du droit n'a revu les
   références, conclure « test technique préliminaire », pas « fiable ».

## Tests logiciels

Les tests unitaires dédiés aux métriques, au rapprochement des références, au
mode lecture seule et à la structure des exemples vérifient des invariants de
code. À la mise à jour du 2026-10-19, la suite complète `.venv/bin/pytest -q`
donne 319 tests réussis et 2 ignorés. `compileall` et `git diff --check`
passent également. Ces résultats ne démontrent pas la validité juridique des
étiquettes ni la qualité du modèle.
Ces vérifications ne démontrent pas la validité juridique des étiquettes ni la
qualité du modèle.
