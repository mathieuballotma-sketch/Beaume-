# Journal de reconstruction de Beaume

Chronologie du projet. Chaque entrée raconte **ce qu'on a fait**,
**pourquoi**, et **ce qui a coincé** le cas échéant.

---

## 2026-10-08 — Fondations (Phase 0)

**Objectif** : poser les bases propres du projet avant toute ligne de code métier.

**Ce qu'on a fait :**
- Créé l'arborescence complète : `beaume/`, `data/`, `tests/`, `docs/`, `scripts/`.
- Installé Python 3.12.15 via Homebrew (le Python système 3.9 était trop ancien).
- Créé le `.venv` isolé dans le projet.
- Écrit `.gitignore` pour exclure `data/`, `.venv/`, `__pycache__/`.
- Centralisé les chemins dans `beaume/config/paths.py`.
- Mis en place un logger rotatif (5 Mo × 5 fichiers) dans `data/logs/`.
- 4 tests verts.

**Décision clé** : le code ne touche jamais `data/` en dur. Il passe toujours
par `config/paths.py` pour garantir que les données clients ne partent jamais
dans Git.

---

## 2026-10-08 — Ontologie juridique

**Objectif** : traduire le vocabulaire du droit en vocabulaire du code, une fois
pour toutes, avant d'écrire quoi que ce soit d'autre.

**Ce qu'on a fait :**
- `IdentifiantLegifrance` : format strict `LEGIARTI/LEGITEXT/JURITEXT + 12 chiffres`.
- `VersionArticle` : immuable, porte un intervalle de dates.
- `Article` : agrège toutes les versions + méthode `version_a(date)`.
- `Citation` : ce que le LLM produit, porte **toujours** une date de référence.
- `ResultatVerification` : verdict du vérificateur (valide / introuvable / abrogé / différent).
- 14 tests verts.

**Décision clé** : un identifiant n'est JAMAIS le numéro humain. `L. 1234-1` est
un alias. L'identifiant vrai, c'est `LEGIARTI000006900898`. Pourquoi ? Parce
qu'un même numéro peut désigner des articles différents selon le code, et un
article peut changer de numéro au fil du temps (recodification).

---

## 2026-10-08 — Ports et machine à états

**Objectif** : rendre le projet extensible sans tout reconstruire à chaque ajout.

**Ce qu'on a fait :**
- Port `Extracteur` (Protocol) : contrat unique, ne connaît aucun format.
- `RegistreExtracteurs` : ajout d'un format sans modifier le pipeline.
- `EtatDocument` : 7 états fermés + ECHEC.
- `Document` : transitions verrouillées, historique horodaté.
- 10 tests verts.

**Décision clé** : aucune ligne `if suffix == ".pdf"` dans le pipeline. On
demande au registre. Comme ça, ajouter un `.docx` ou un `.eml` demain ne touche
ni au pipeline ni aux tests existants.

**Décision clé** : les 6 lois d'architecture sont posées :
1. Dépendance descendante (L5 → L0).
2. Conservation de l'information (chaque transformation traçable).
3. Tiers exclu (machine à états fermée).
4. Inversion des dépendances (Ports + Adapters).
5. Composition fermée (une porte d'entrée par module).
6. Pureté au cœur, effets aux bords.

---

## 2026-10-08 — Organisation Cursor + Git

**Objectif** : avoir un environnement de travail propre et un historique Git.

**Ce qu'on a fait :**
- Configuré `.vscode/` (interpréteur, pytest, extensions recommandées).
- `docs/ARCHITECTURE.md` avec diagrammes Mermaid.
- `docs/DECISIONS.md` pour tracer les décisions.
- `README.md` avec checklist de progression.
- `git init` + premier commit.

**Ce qui a coincé :** un fichier `DECISIONS.md$` (avec un `$` parasite) a été
créé par un copier-coller malencontreux. Corrigé par `rm "docs/DECISIONS.md\$"`
puis recréation.

---

## 2026-10-08 — Phase 1 : Extracteur PDF

**Objectif** : premier vrai adaptateur respectant un port.

**Ce qu'on a fait :**
- `extract_pdf_text(path)` bas niveau (via `pymupdf`).
- `ExtracteurPDF` : l'adaptateur qui respecte le contrat `Extracteur`.
- 5 tests verts.

**Ce qui a coincé :** `fitz` est déprécié par PyMuPDF. Le code utilise
désormais `import pymupdf` directement. Les warnings SWIG ont été masqués
dans `pyproject.toml`.

---

## 2026-10-08 — Phase 2 : Lecteur de dossier

**Objectif** : parcourir un dossier client complet.

**Ce qu'on a fait :**
- `LecteurDossier` : parcourt, choisit le bon extracteur via le registre,
  ignore les fichiers cachés, respecte l'ordre alphabétique.
- `FichierExtrait`, `ResultatDossier` avec compteurs.
- 6 tests verts.

---

## 2026-10-08 — Phase 3 : Chunker

**Objectif** : découper un texte long en morceaux exploitables.

**Ce qu'on a fait :**
- `decouper()` : fonction pure, respecte les frontières de paragraphes,
  chevauchement configurable, coupe brute si paragraphe énorme.
- `Chunk` : index, texte, positions source.
- 10 tests verts, dont un test de **déterminisme**.

---

## 2026-10-08 — Phase 4 : Chunking intégré

**Objectif** : brancher le chunker dans le lecteur de dossier.

**Ce qu'on a fait :**
- `LecteurDossier` produit les chunks en plus du texte brut.
- `FichierExtrait.chunks` est un **tuple** (immuable).
- 4 tests supplémentaires verts.

---

## 2026-10-10 — Phase 5a : Encodeur

**Objectif** : transformer du texte en vecteurs (embeddings).

**Ce qu'on a fait :**
- Port `Encodeur` (dimension + encoder).
- `EncodeurOllama` : utilise `bge-m3` en local.
- `FauxEncodeur` pour les tests : déterministe, aucun service externe.
- Test Ollama **skippable** : si Ollama n'est pas lancé, le test se saute
  sans casser la suite.
- 6 tests (5 verts + 1 skippé).

**Décision clé** : jamais un test ne doit dépendre d'un service externe.
On met un `@pytest.mark.skipif` qui détecte Ollama automatiquement.

---

## 2026-10-12 — Phase 5b : Index vectoriel

**Objectif** : pouvoir stocker et rechercher des vecteurs par similarité.

**Ce qu'on a fait :**
- Port `IndexVectoriel` (ajouter, rechercher, taille, vider).
- `IndexMemoire` : fake déterministe pour les tests, distance cosinus.
- `IndexLanceDB` : persistance sur disque.
- 12 tests verts (faux index + intégration LanceDB).

**Ce qui a coincé :**
1. `table_names()` déprécié → remplacé par `list_tables()`.
2. `list_tables()` retourne un objet, pas une liste → cassé le test de
   persistance. Solution : `create_table(..., exist_ok=True)` qui ouvre
   si existe, crée sinon.
3. Le `test_ingestion.py` (phase 5c) a été créé alors que `ingestion.py`
   n'existait pas, bloquant toute la suite pytest. Solution : suppression
   du test orphelin, il sera recréé avec son module.

**Décision clé** : on ne garde que du vert dans pytest. Un test qui échoue
parce que son module n'existe pas, c'est une dette qu'on supprime
immédiatement.

---

## En cours

**Phase 5c** : pipeline d'ingestion `dossier → chunks → encodeur → index`.
À reprendre dans Cursor. Le fichier `ingestion.py` et son test seront créés
ensemble, proprement.
## 2026-10-12 — Premier test bout-en-bout reussi

**Premier dossier client traite de bout en bout.**

Dossier : `data/inbox/dossier_test_001/lettre_client.pdf` (1950 octets, 2 pages)
Date de reference : 2026-10-12
Pipeline : extraction PDF -> chunking -> analyse LLM -> verification -> Markdown

**Resultats** :
- 1385 caracteres extraits, 3 chunks
- 4 articles candidats trouves dans le corpus
- LLM qwen2.5:7b-instruct : 1044 tokens prompt, 378 tokens reponse
- **22.58 secondes au total** (99.99% dans le LLM)
- 2 citations valides, 0 rejetees
- Rapport ecrit dans `data/out/dossier_test_001_analyse.md`

**Ce qui marche** :
- Le pipeline va de bout en bout sans erreur.
- Le LLM produit du JSON valide du premier coup.
- Le verificateur confirme les 2 citations (L. 1232-1, L. 1152-1).
- Le Markdown est lisible et professionnel.

**Ce qu'on doit ameliorer** :
- Corpus trop limite (5 articles), enrichir a 20-30.
- Le LLM garde les accents dans l'extrait cite alors que le corpus n'en a pas
  (cosmetique, le verificateur normalise).
- Petite faute de grammaire dans une question ("Sont-les agissements" au lieu
  de "Les agissements sont-ils"), a corriger dans le prompt.

**Verification** : 180 tests verts, 0 skipped (Ollama operationnel).
