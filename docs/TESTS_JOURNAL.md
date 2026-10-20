# Journal des tests — Beaume

Chronologie des tests lances sur le projet, avec sorties brutes du
terminal. Ce document sert a :

- Comprendre ce qui a ete teste, quand, et pourquoi.
- Voir les resultats bruts (succes, echecs, mesures).
- Reproduire les tests sur une autre machine.
- Suivre l'evolution du comportement du LLM.

## Vérification code du 2026-10-19

Commande exécutée depuis `/Users/mathieubellot/Projets/beaume` :

```bash
TMPDIR=/private/tmp PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/pytest -q
```

Résultat : **319 passed, 2 skipped** en 24,27 s. Les tests Ollama réels ont
été ignorés car le service local n'était pas accessible depuis l'environnement
de vérification. `python -m compileall -q beaume scripts tests` et
`git diff --check` ont réussi.

Le nouveau `scripts/verifier_dataset.py` a aussi audité un échantillon de cinq
lignes de l'ancien `data/entrainement/train_llm.jsonl` : **5/5 erreurs de
structure**, car ces lignes ne contiennent pas le marqueur de dossier/candidat
du nouveau contrat à base d'`article_id`. Aucun jeu `train_llm_v2.jsonl` ni son
manifeste correspondant n'a été produit pendant cette vérification : la
génération Ollama n'a pas été exécutée.

Ces tests confirment des invariants logiciels. Ils ne valident ni les faits
synthétiques, ni la pertinence des articles, ni une fiabilité juridique.

---

## Etat au 2026-10-16 (fin de session)

- 261 tests passent.
- 12 commits depuis le debut de la session.
- Tracabilite pages operationnelle (extracteur, chunker, prompt, rapport).
- Mode JSON natif Ollama active.
- Citation valide sur dossier simple (dossier_test_001).
- Bug identifie : le LLM invente des noms de fichiers sur dossier complexe.

---

## 1. Audit du corpus legi_full.sqlite

### Commande

    python scripts/auditer_corpus.py

### Sortie brute

    === Schema ===
      Table : articles
      Table : versions
      Table : articles_fts
      Table : articles_fts_data
      Table : articles_fts_idx
      Table : articles_fts_content
      Table : articles_fts_docsize
      Table : articles_fts_config

    === Compteurs ===
    Articles distincts : 25767
    Versions totales   : 25767

    === Distribution versions/article ===
        1 version(s) : 25767 article(s)

    === Codes couverts ===
      code_travail          : 11433 articles
      code_securite_sociale : 7245 articles
      code_civil            : 2883 articles
      code_consommation     : 2139 articles
      code_procedure_civile : 2067 articles

    === Plage temporelle ===
      Date min : 1803-08-03
      Date max : 2025-07-11

### Interpretation

Le corpus ne contient qu'une seule version par article. Impossible
de verifier la version historique d'un article a une date anterieure
a 2025. Limite documentee dans docs/PROMESSES.md section 3.7.

---

## 2. Audit du dataset HuggingFace source

### Commande

    python scripts/auditer_dataset_hf.py

### Sortie brute

    Chargement /Users/mathieubellot/Projets/beaume/data/legal/legi_2025...
    Lignes totales : 367075
    Colonnes : article_id, article_identifier, article_num,
    article_contenu_text, article_contenu_markdown, texte_titre,
    texte_nature, texte_cid, article_etat, texte_date_publi,
    date_debut, date_fin, texte_contexte

    Scan de 367075 lignes pour analyse...

    === Etats ===
      VIGUEUR              : 367075

    === Articles ===
    Articles distincts : 367071
    Lignes scannees    : 367075
    Ratio versions/article : 1.00

    === Plage temporelle ===
    date_debut min : 1539-08-25
    date_debut max : 2999-01-01
    date_fin min   : 2025-03-01
    date_fin max   : 2999-01-01

### Interpretation

Le dataset VinceGx33/legi-french-law-2025 ne contient qu'une version
par article. La superposition des versions est impossible avec ce
dataset.

---

## 3. Decouverte du dataset Etalab

### Commande

    python -c "
    from datasets import load_dataset
    ds = load_dataset('AgentPublic/legi', split='train')
    print(f'Lignes : {len(ds)}')
    rows = [r for r in ds if r['number'] == 'L1235-3']
    for r in rows[:5]:
        print(r['doc_id'], r['start_date'], r['end_date'], r['status'])
    "

### Sortie brute

    Lignes : 2198872
    Colonnes : chunk_id, doc_id, chunk_index, chunk_xxh64, nature,
    category, ministry, status, title, full_title, subtitles,
    number, start_date, end_date, nota, links, text, chunk_text,
    embeddings_bge-m3
    doc_id=LEGIARTI000006686189 start=2000-06-22 end=2004-08-07 status=TRANSFERE
    doc_id=LEGIARTI000006686190 start=2004-08-07 end=2999-01-01 status=VIGUEUR
    doc_id=LEGIARTI000006901142 start=2008-05-01 end=2017-09-24 status=MODIFIE
    doc_id=LEGIARTI000035643453 start=2017-09-24 end=2018-04-01 status=MODIFIE

### Interpretation

Le dataset AgentPublic/legi (produit par Etalab, gouvernement
francais) contient 4 versions historiques de l'article L1235-3.
C'est la solution au probleme des versions historiques. Integration
prevue mais non terminee.

---

## 4. Tests apres chaque commit

### Commit 71c960b — Signaux d'echec

    ============================= 244 passed in 24.21s =============================

Ajout : Analyse.erreur, Analyse.fichiers_ignores, Analyse.etat
(COMPLET, PARTIEL, ECHEC). Tests ajoutes : test_analyse_etat.py (5),
test_rapport_etat.py (3).

### Commit 88d1ec8 — Extracteur PDF pagine

    collected 5 items
    tests/unit/test_extracteur_pdf_pages.py PASSED
    ============================= 250 passed in 24.37s =============================

Ajout : PageExtraite, extraire_avec_pages().

### Commit 7d5d1d8 — Propagation pages dans Ficait

    ============================= 253 passed in 24.08s =============================

Ajout : FichierExtrait.pages. Appel a extraire_avec_pages().

### Commit c7bdf59 — Propagation pages dans Chunk

    collected 4 items
    tests/unit/test_chunker_pages.py PASSED
    ============================= 257 passed in 24.04s =============================

Ajout : Chunk.fichier, Chunk.page_debut, Chunk.page_fin.
Fonction decouper_pages().

### Commit 43c192e — Pages dans les citations

    collected 4 items
    tests/unit/test_citation_pages.py PASSED
    ============================= 261 passed in 24.93s =============================

Ajout : Citation.pages, Citation.fichier.

### Commit e67abe7 — Mode JSON natif + prompt court

    OK 3 fichiers
    ============================= 261 passed in 26.20s =============================

Ajout : SCHEMA_ANALYSE dans generateur_ollama.py, prompt reduit a
~400 tokens, dossier place avant les regles.

---

## 5. Analyses reelles sur dossiers

### Analyse 1 — Dossier simple, prompt initial

    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_test_001 2024-01-01

    INFO | lecteur_dossier | Extrait : lettre_client.pdf (2 pages, 1385 caracteres, 3 chunks)
    INFO | analyse_dossier | Analyse : 3 chunks, 15 articles candidats
    INFO | generateur_ollama | Generation qwen2.5:7b-instruct : 4090 tokens prompt, 269 tokens reponse, 34.59 s
    INFO | pipeline | Pipeline termine : 1 citations (0 valides, 1 rejetees) en 34.83 s

Resultat : 0 valides, 1 rejetee (texte_different). Source :
lettre_client.pdf (page(s) 1). Extrait reformule.

Interpretation : tracabilite OK, mais Qwen reformule.

### Analyse 2 — Dossier simple, prompt renforce v2

    INFO | generateur_ollama | Generation qwen2.5:7b-instruct : 2050 tokens prompt, 244 tokens reponse, 21.55 s
    INFO | pipeline | Pipeline termine : 1 citations (0 valides, 1 rejetees) en 21.79 s

Resultat : 0 valides, 1 rejetee. Source : lettre_client.pdf (page(s) ?).
Extrait reformule.

Interpretation : regression. Le prompt long degrade la tracabilite.

### Analyse 3 — Dossier simple, mode JSON natif v3

    INFO | generateur_ollama | Generation qwen2.5:7b-instruct : 3577 tokens prompt, 299 tokens reponse, 32.66 s
    INFO | pipeline | Pipeline termine : 2 citations (2 valides, 0 rejetees) en 32.95 s

Resultat : 2 valides, 0 rejetee. Extraits litteraux (L1152-1 et
L1232-1). Source : lettre_client.pdf (page(s) 1).

Interpretation : premier run reussi.

### Analyse 4 — Dossier multi-fichiers (5 PDFs)

    INFO | lecteur_dossier | Extrait : bulletins_salaire.pdf (1 pages, 374 caracteres, 1 chunks)
    INFO | lecteur_dossier | Extrait : courrier_direction.pdf (1 pages, 584 caracteres, 1 chunks)
    INFO | lecteur_dossier | Extrait : lettre_client.pdf (1 pages, 1245 caracteres, 3 chunks)
    INFO | lecteur_dossier | Extrait : ordonnance_refere.pdf (1 pages, 455 caracteres, 1 chunks)
    INFO | lecteur_dossier | Extrait : temoignages_collegues.pdf (1 pages, 621 caracteres, 2 chunks)
    INFO | analyse_dossier | Analyse : 8 chunks, 38 articles candidats
    INFO | generateur_ollama | Generation qwen2.5:7b-instruct : 2050 tokens prompt, 624 tokens reponse, 40.75 s
    INFO | pipeline | Pipeline termine : 3 citations (2 valides, 1 rejetees) en 41.06 s

Resultat : 2 valides, 1 rejetee. Bug identifie : le LLM cite
conclusions.pdf (page 3) alors que ce fichier n'existe pas dans le
dossier. Le LLM a invente un nom de fichier.

Interpretation : la tracabilite multi-fichiers fonctionne pour les
valides. Bug a corriger : injecter la liste des vrais fichiers dans
le prompt.

---

## 6. Comment relancer ces tests

    pytest -v 2>&1 | tail -3
    pytest tests/unit/test_citation_pages.py -v
    python scripts/auditer_corpus.py
    python scripts/auditer_dataset_hf.py
    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_test_001 2024-01-01
    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_gros_001 2024-01-01
    diff data/out/dossier_test_001_analyse_v1.md data/out/dossier_test_001_analyse.md

---

## 7. Points d'attention

1. Ollama doit tourner : curl -s http://localhost:11434/api/tags
2. Le corpus doit exister : data/vector/legi_full.sqlite (~62 Mo)
3. Qwen 7B est sensible a la longueur du prompt : au-dela de ~750
   tokens, il ignore les premieres instructions.
4. Le mode JSON natif d'Ollama force la structure mais pas la
   veracite. Le LLM peut inventer un nom de fichier.
