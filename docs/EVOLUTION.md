# Evolution de Beaume — Problemes et Idees

Ce document consigne deux choses distinctes :
1. Les problemes rencontres et comment ils ont ete resolus.
2. Les idees pour Beaume, proposees et leur etat.

Sert de memoire vive pour tout assistant qui reprend le projet.

---

## PARTIE 1 — PROBLEMES RENCONTRES ET RESOLUTIONS

| # | Probleme | Cause | Resolution | Commit |
|---|---|---|---|---|
| P-001 | Heredocs qui foirent sur longs fichiers | Caracteres speciaux casses par le shell | Basculer sur Cursor pour les gros fichiers | — |
| P-002 | `fitz` deprecie par PyMuPDF | Changement d'API | `import pymupdf` | — |
| P-003 | Fichier `DECISIONS.md$` avec `$` parasite | Copier-coller accidentel | `rm "docs/DECISIONS.md\$"` | — |
| P-004 | `table_names()` deprecie dans LanceDB | Changement d'API | `list_tables()` puis `create_table(exist_ok=True)` | — |
| P-005 | `test_ingestion.py` orphelin bloquait pytest | Fichier cree sans son module | Supprime, recree avec le module | — |
| P-006 | `python` et `pip` absents du venv | Prompt `((.venv) )` decoratif | Activer manuellement | — |
| P-007 | Token GitHub colle dans le chat | Erreur humaine | Revoque + nouveau token | — |
| P-008 | Selecteur dupliquait les chunks | Chaque chunk apparaissait dans 4 questions | Assignation a question dominante | `ded9a56` |
| P-009 | `L. 1234-1` non trouve dans corpus DILA | Formats differents (avec/sans espaces et points) | Module `normalisation.py` | `b51c05a` |
| P-010 | `pyproject.toml` sans dependances | Oubli initial | 7 dependances reelles + extra dev | `c5a1e39` |
| P-011 | Deux corpus cohabitaient (demo et prod) | Scripts pointaient sur des bases differentes | Bascule explicite (`legi_full.sqlite` + `BEAUME_CORPUS_DEMO`) | `1336c64` |
| P-012 | 5 dossiers morts a la racine de `beaume/` | Anciennes versions avant refonte | Supprimes + fusion extraction PDF dans adapters | `607a8b2` |
| P-013 | README obsolete (200 tests, pas de corpus) | Jamais mis a jour | Reecriture complete | `576fa0d` |
| P-014 | LLM non deterministe (2/3 puis 0/3 valides) | Temperature = 0.1 | Temperature = 0.0 | `ec3245a` |
| P-015 | Citation sans extrait validee | `if citation.extrait:` saute la verification | Verdict `EXTRAIT_MANQUANT` | `be34dd5` |
| P-016 | Test d'idempotence faible (placeholder binaire) | Ne verifiait pas la validite de la base | Vraie mini-base SQLite + relecture apres script | `877fbdd` |
| P-017 | JURI retire du serveur OPENDATA DILA | Migration vers API Judilibre | Dataset HuggingFace `antoinejeannot/jurisprudence` | — |
| P-018 | Visas dans le texte, pas dans le champ `visa` | Format DILA des decisions recentes | Regex sur le texte (62% extractibles) | — |
| P-019 | Bench qualite : 20% de rappel | Chercheur FTS5 inadapte (mots-cles vs sens) | En cours : embedding specialise | — |
| P-020 | Augmenter la limite de 5 a 20 candidats aggrave | Le LLM est noye par 20 articles dont aucun n'est le bon | A revoir apres embedding | — |
| P-021 | 30-40% d'un dossier reel sont des images non lues | Extracteur PDF ne lit que le texte natif | Module vision (a faire) | — |

### Problemes ouverts (non resolus)

| # | Probleme | Gravite |
|---|---|---|
| A1 | Verificateur valide des articles hors sujet (existence, pas pertinence) | Critique |
| A2 | LLM hallucine le contenu des articles (prefere sa memoire) | Critique |
| A3 | Chercheur FTS5 = 20% de rappel | Critique |
| A4 | PDF scannes / images non lus (70% d'un dossier reel) | Critique |
| B1 | Corpus historique absent (une seule version par article) | Important |
| B2 | Selecteur assigne chaque chunk a une seule question dominante | Important |
| C1 | Performance a l'echelle (dossier 200 pages non teste) | Latent |
| C2 | Ollama sur Mac 8 Go : ne passera pas avec 7B | Latent |
| C3 | SQLite concurrent (un seul writer) | Latent |
| C4 | Liens Legifrance non verifies (contradiction offline) | Latent |
| C5 | Licence : verification reseau contredit "aucune donnee ne sort" | Latent |
| C6 | RGPD : logs contiennent extraits clients ? | Latent |
| C7 | Tests d'integration skippes en CI (corpus absent) | Latent |
| C8 | Dependance a un dataset HF tiers (peut disparaitre) | Latent |
| C9 | Pas de versionnage du corpus | Latent |
| C10 | Un seul modele LLM pour tout (pre-analyseur a venir) | Latent |

---

## PARTIE 2 — IDEES POUR BEAUME

### Premiere vague (avant 2026-10-13)

| # | Idee | Logique extraite | Traduction | Etat |
|---|---|---|---|---|
| I-001 | "Etat de superposition, il prend de la place que quand on en a besoin" | Cout nul tant qu'inactif | Lazy loading. SQLite natif. DepotMultiple a prevoir | Concept acte |
| I-002 | "L'eau qui trouve toujours son chemin" | Flux mono-directionnel | Pipeline DEPOSE -> EXTRAIT -> DECOUPE -> INDEXE -> ANALYSE -> VERIFIE -> PUBLIE | Fait |
| I-003 | "La cuisine" | Ingredients bruts transformes par etapes | Etapes typees qui s'enchainent | Fait |
| I-004 | "Un petit LLM qui regarde en premier puis un plus gros" | Cascade leger -> lourd | Selecteur -> pre-analyseur 0.5b -> generateur 7bssier n'est jamais mono-domaine" | Multi-label | Classificateur multi-label + profils YAML | A faire |
| I-006 | "Il faut qu'on sache sur quoi il s'appuie" | Tracabilite des sources | Section Sources dans le rapport | Partiel |
| I-007 | "Il peut le structurer pour que ce soit sa facon de travailler" | Chaque avocat a sa methode | Profils YAML personnalisables | A faire |
| I-008 | "J'avais deja fait un HUD avec les API Apple" | Reutiliser le travail | Code PyObjC/AppKit de Lucie | Phase 3 |
| I-009 | "Un abonnement mensuel abordable, paiement securise" | Paiement securise, aucune donnee client | Stripe + jeton signe 40 jours | Documente |
| I-010 | "Verifiable sur ce que devient l'argent" | Transparence financiere | Rapport financier + votes utilisateurs | Documente |
| I-011 | "Pas pour remplacer, faire gagner du temps" | L'avocat decide | Notes de transparence dans chaque rapport | Fait |
| I-012 | "Des centaines voire milliers de tests" | Mesurer avant d'optimiser | `bench_recherche.py` | Fait |
| I-013 | "Une petite IA locale qui prend presque aucune place" | Pre-traitement leger | Pre-analyseur qwen2.5:0.5b (~400 Mo) | A faire |
| I-014 | "Scorer les chunks puis envoyer au petit LLM puis au gros" | Pre-resume hierarchique | Selecteur -> pre-analyseur -> generateur | 1/3 fait |
| I-015 | "Prendre la logique du concept, pas le reproduire" | Traduire la metaphore en logique | Methode de communication actee | Fait |

### Deuxieme vague (2026-10-13 / 2026-10-14)

| # | Idee | Logique extraite | Traduction | Etat |
|---|---|---|---|---|
| I-016 | "Le HUD se met dans un coin, dit ce qu'elle fait, un point quand l'action vient" | Assistant, pas application. Pas d'animation couteuse | Evenements d'etape pipeline -> HUD | Note |
| I-017 | "Fiabilite d'abord, vitesse ensuite" | Mesurer avant d'optimiser | Bench avant toute optimisation | Fait |
| I-018 | "Numeroter un texte de loi avec un calcul deterministe 0 ou 1" | Numero = vecteur. Adresse binaire 64 bits | Calculateur d'adresse (apres 500k articles) | Note |
| I-019 | Bitmap de presence 0/1 | 1 bit par article possible | Detection de nouveaute/abrogation | Note |
| I-020 | Hash de contenu par version | Detection de changement instantanee | xxHash64 sur chaque version | Note |
| I-021 | Decouper les 3M de documents en zones logiques | Nature / domaine / frequence | DepotComposite par zone | Note |
| I-022 | "Si Beaume etait la calculatrice deterministe des textes de lois" | Moteur de regles faits -> articles | Change la nature du projet. Decision a froid | Note |
| I-023 | "Une fonction qui marche qu'une seule journee et qui efface tout" | Veille quotidienne, avance sans reculer | DILA + bitmap + hash | Note |
| I-024 | "Elle envoie une notification pour avoir l'autorisation" | Demander avant de lire | Notif HUD + choix utilisateur | Note |
| I-025 | "Mise a jour sans que l'avocat manipule" | Proposer, l'avocat accepte | UX HUD | Note |
| I-026 | "On prend les 3M de textes et on entraine le modele" | Modele specialise juridique | Romulus / Jargon + fine-tuning | Note |
| I-027 | "Un modele qui se specialise vers un domaine quand il a l'information" | LoRA adapters par domaine | Modele de base + LoRA. Charge a la demande | Note |
| I-028 | "Avant que le LLM soit utilise, qu'il sache quelle zone activer grace au chunk" | Detection de domaine avant LLM | 3 niveaux (mots-cles, classifieur, petit LLM) | Note |
| I-029 | "Quand il detecte une photo il active un modele et il explique ce que la photo est" | Vision a la demande. Image -> description -> vecteur | ExtracteurVision + Ministral 3B | Note |

### Idees cote assistant, adoptees

- Les 6 lois d'architecture.
- La machine a etats (DEPOSE -> ... -> PUBLIE).
- Les ports (Protocol) et adaptateurs.
- L'ontologie juridique (Article, VersionArticle, Citation, ResultatVerification, IdentifiantLegifrance).
- Les faux composants pour les tests (FauxEncodeur, FauxGenerateur, IndexMemoire, FauxChercheur).
- Le profiler @chronometre.
- Le selecteur de chunks par question dominante.
- Le benchmark FTS5 par self-retrieval.
- La normalisation des numeros DILA <-> humain.
- Le verdict EXTRAIT_MANQUANT.

---

## ETAT ACTUEL

- Tests : 233 verts.
- Bench qualite : 20% de rappel sur 5 dossiers.
- Duree moyenne analyse : 56 s.
- Corpus LEGI : 367 075 articles (723 Mo).
- Corpus jurisprudence : 1 125 968 decisions (14 Go).
  - 29 551 chambre sociale recentes (2015+).
- Paires extractibles estimees : 5 000-10 000.
- Ollama : bge-m3, qwen2.5:7b-instruct, qwen2.5:0.5b.

---

## PLAN ACTUEL

1. Ameliorer FTS5 (synonymes, expansion). Mesurer. Gain attendu : 20% -> 35-45%.
2. Construire le dataset d'entrainement (5 000-10 000 paires).
3. Reecrire en style client via API gratuite.
4. Fine-tuner un modele d'embedding (Romulus ou bge-m3).
5. Integrer dans Beaume, relancer le bench. Gain attendu : 35% -> 70-85%.

Perimetre de demarrage : licenciement economique uniquement.

Architecture cible : modele de base + LoRA adapters par domaine. Detection du domaine via les chunks avant l'appel LLM.

---

## VOIR AUSSI

- docs/DECISIONS.md — decisions actees
- docs/JOURNAL.md — chronologie detaillee
- docs/ARCHITECTURE.md — diagrammes
- docs/PROMPT_BEAUME.md — methode et vision

## 2026-10-14 (suite) — Test sur dossier reel

- **Bench simple (5 dossiers courts)** : 80 % de rappel apres fix
  (mots-cles elargis + limite 5 + prompt strict).
- **Dossier reel (1 391 car., Cour de cassation)** : pipeline
  fonctionne (3 chunks, 14 candidats, 3 citations produites, 2 valides).
  MAIS les articles cites sont **hors sujet** (L1235-7 prescription,
  L1233-67 CSP) au lieu des articles sur la procedure collective,
  la validite d'acte en periode suspecte et les indemnites de rupture.
- **Conclusion** : la pertinence reste le probleme n1. Le bench simple
  est trop propre. Il faut un bench sur vrais dossiers avec ground truth.
- **Prochain chantier** : embedding specialise (Piste B) sur les
  29 551 decisions de la chambre sociale.
