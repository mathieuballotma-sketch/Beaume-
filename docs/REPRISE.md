# Reprise de session — Beaume

Derniere mise a jour : 2026-10-14

## Etat Git

Dernier commit : 748966b
Branche : main (a jour avec origin)
Tests : 235 passed
Bench qualite : 80 % (5 dossiers simples)
Bench dossier reel : fonctionne techniquement, pertinence non mesuree

## Ce qui vient d'etre fait (2026-10-14)

1. Fix extraction de mots-cles (stopwords elargis, limite 200).
2. Fix prompt (format strict + exemple few-shot + rappel fin).
3. Limite candidats FTS5 : 20 -> 5.
4. Bench simple : 20 % -> 80 %.
5. Test sur dossier reel : pipeline OK, mais articles hors sujet.

## Probleme n1 : PERTINENCE

Le LLM respecte le format, produit des citations valides. Mais il
choisit les articles contenant la formule litterale au lieu de ceux
qui repondent a la question juridique.

## Piece maitresse : le moteur de recherche semantique

Architecture cible :
  1. Comprendre  : LLM extrait les concepts du dossier
  2. Chercher    : embedding specialise (SENS, pas mots-cles)
  3. Verifier    : verificateur existant + score

## Donnees disponibles

- data/legal/legi_2025 : 367 075 articles (723 Mo)
- data/legal/jurisprudence : 1 125 968 decisions (14 Go)
  - 29 551 chambre sociale 2015+
  - Paires (faits, articles) extractibles : 5 000-10 000

## Plan d'attaque

1. Extraire les paires (faits, articles) depuis les decisions.
2. Generer des exemples "style client" via API gratuite (Groq, Cerebras).
3. Fine-tuner un modele (Romulus, bge-m3) sur Kaggle/Colab.
4. Integrer ChercheurEmbedding dans Beaume.
5. Relancer le bench. Gain attendu : 80 % -> 90 %+.

## Fichiers cles

- beaume/application/analyse_dossier.py (limite 5)
- beaume/application/prompts.py (format strict)
- beaume/utils/texte.py (stopwords, limite 200)
- beaume/adapters/chercheur_articles_fts5.py (max_mots_cles 200)
- scripts/bench_qualite.py (mesure du rappel)
- beaume/bench/dossiers_test.json (5 dossiers de test)
