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

## Mesure gelée du 20 octobre 2026 (Phase 1)

**Statut** : mesure de référence pour la Phase 2 (élargissement du jeu).

**Corpus** : `data/vector/legi_full_v2.sqlite`
- SHA256 : `3e86c3931e8d6026904b85931701edecc93ab38c73eae35d1158ee75bdd37a30`
- 43 794 articles, 92 767 versions, 22 269 articles multi-versions
- 5 statuts : `en_vigueur` 25 652, `abroge` 20 110, `modifie` 46 067, `futur` 482, `inconnu` 456
- 5 codes : travail, civil, sécurité sociale, consommation, procédure civile
- Reconstruction depuis `data/vector/legi_dila_v2/legi_dila.sqlite` (DILA, 468 archives, Licence Ouverte 2.0)

**Corpus v1 (référence historique)** : `data/vector/legi_full.sqlite`
- SHA256 : `033034f674846ac8a3a23be22e7a127a5aabeb9ed68cfe2514aa14fce4ab4abb`
- 25 767 articles, 25 767 versions, toutes `en_vigueur`

**Modèle** : `qwen2.5:7b-instruct` (le modèle de base, pas le finetuné `qwen-beaume-v1`)

**Jeu de test** : `beaume/bench/dossiers_test.json` version 3
- 5 dossiers, dont 1 marqué `disputed` (BE-LECO-002)
- `limite_articles=10` par chunk, `limite_candidats=10` au total
- Annotations `provisoires_non_validees_par_un_juriste`

**Résultat du score principal** (dossiers `provisoire`, non `disputed`) :
- 4 dossiers
- Rappel micro `must_cite` : **100,0 %** (4/4)
- Rappel macro `must_cite` : 100,0 %
- Retrieval `must_cite` : 100,0 %
- Citations rejetées : 0
- Erreurs d'exécution : 0
- Durée moyenne : 5,8 s/dossier

**Résultat des dossiers `disputed`** (pour information, non comptés) :
- 1 dossier (BE-LECO-002)
- Rappel micro `must_cite` : 0,0 % (0/2)
- Retrieval `must_cite` : 0,0 %

**Interprétation** :
- Le score principal 4/4 est une baseline mesurable sur 4 dossiers non contestés. Ce n'est pas une validation juridique : les annotations sont provisoires, le jeu est petit, et 4 dossiers ne permettent pas de conclure.
- BE-LECO-002 est marqué `disputed` : L1233-61 (seuil PSE : 50 salariés et 10 licenciements dans 30 jours) contient les nuggets pour répondre à la question du dossier (6 salariés, 2 licenciements, pas de PSE). Les `must_cite` annotés (L1233-1, L1233-2) sont des articles généraux qui ne répondent pas à la question du PSE, et ils ne sont pas récupérés par FTS5 même avec `limite_articles=10`. BGE-M3 et 2/3 LLM choisissent L1233-61. En attente de relecture par un juriste.
- Le score disputed (0/2) documente un échec mesuré, pas une erreur de Beaume : le modèle ne peut pas trouver des articles qui ne sont pas les bons.

**Fichiers de référence** :
- `docs/GEL.md` : liste des artefacts gelés (corpus, jeu, métriques) avec hashes
- `data/logs/bench_qualite_v2_7b_l10_gel.json` : rapport JSON de cette mesure
- Commande : `.venv/bin/python scripts/bench_qualite.py --modele qwen2.5:7b-instruct --base data/vector/legi_full_v2.sqlite --sortie data/logs/bench_qualite_v2_7b_l10_gel.json`

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