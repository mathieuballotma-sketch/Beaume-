# Beaume

Assistant juridique 100% local pour avocats francais.

Promesse : aucune donnee client ne quitte votre machine. Jamais.

---

## Etat actuel (2026-10-16)

Prototype avance. Non utilisable en production. L'etat est documente
dans docs/PROMESSES.md.

- 261 tests passent.
- Pipeline complet : dossier PDF -> extraction -> analyse LLM ->
  verification -> rapport Markdown.
- Tracabilite : chaque citation indique le fichier et la page source.
- Verification : 6 verdicts (VALIDE, INTROUVABLE, VERSION_INCORRECTE,
  ABROGE, TEXTE_DIFFERENT, EXTRAIT_MANQUANT).
- Etats de rapport : COMPLET, PARTIEL, ECHEC.

---

## Documentation

| Document | Contenu |
|---|---|
| docs/PROMESSES.md | Journal de bord ethique : ce qu'on promet, ce qu'on ne promet pas |
| docs/TESTS_JOURNAL.md | Toutes les commandes de test lancees, avec sorties brutes |
| docs/LLM_EVOLUTION.md | Evolution des prompts et du comportement du LLM |
| docs/JOURNAL.md | Chronologie du projet |

---

## Installation

### Prerequis

- macOS (Apple Silicon)
- Python 3.12+
- Ollama installe et lance

### Etapes

    git clone https://github.com/mathieuballotma-sketch/Beaume-.git
    cd Beaume-
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    ollama pull qwen2.5:7b-instruct

---

## Commandes essentielles

### Tests

    pytest -v
    pytest tests/unit/test_citation_pages.py -v
    python -c "import ast; ast.parse(open('beaume/application/analyse_dossier.py').read())"

### Analyse d'un dossier

    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_test_001 2024-01-01

### Audit

    python scripts/auditer_corpus.py
    python scripts/auditer_dataset_hf.py

---

## Architecture

    beaume/
      legal/        L2  Ontologie juridique (Article, Citation, Analyse)
      ports/        L1  Contrats (Protocol) - Extracteur, ChercheurArticles,
                        DepotArticles, Generateur, VerificateurCitations
      adapters/     L0  Implementations - PDF, Ollama, SQLite, FTS5
      application/  L3  Orchestration - pipeline, analyse_dossier, chunker
      output/           Rendu Markdown
      config/           Chemins (paths.py)
      testing/          Doublures
      utils/            Logging, profiler

    scripts/
      telecharger_corpus.py        Charge LEGI (25 767 articles, 5 codes)
      analyser_dossier.py          Pipeline complet dossier -> Markdown
      reecrire_faits.py            Reecriture style client (Groq + Ollama)
      construire_dataset_entrainement.py  Paires (anchor, positive)
      split_train_test.py          Split par id_fait
      fusionner_faits.py           Fusion dedoublonnee
      nettoyer_faits.py            Filtre les paires bruitees
      auditer_corpus.py            Audit SQLite
      auditer_dataset_hf.py        Audit dataset HF

---

## Les 6 lois d'architecture

1. Dependance descendante : L5 -> L4 -> L3 -> L2 -> L1 -> L0.
2. Conservation de l'information : chaque transformation tracable.
3. Tiers exclu : machine a etats fermee, pas d'etat intermediaire.
4. Inversion des dependances : Ports (Protocol) + Adapters.
5. Composition fermee : une porte d'entree par module.
6. Purete au coeur, effets aux bords.

Regle d'extension : ajouter une fonctionnalite = 1 fichier + 1 test
+ 0 modification du coeur.

---

## Stack technique

| Composant | Technologie |
|---|---|
| Langage | Python 3.12 |
| LLM | Ollama (qwen2.5:7b-instruct) |
| Recherche articles | SQLite FTS5 |
| Extraction PDF | PyMuPDF |
| Modeles Pydantic | Pydantic v2 |
| Tests | pytest |

---

## Licence

A definir. Usage commercial sur accord.
