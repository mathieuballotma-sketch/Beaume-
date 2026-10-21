# Beaume

Assistant juridique pour avocats francais, concu pour l'analyse locale des dossiers.

L'analyse des dossiers clients est concue pour fonctionner localement, avec
Ollama execute sur votre machine. Les documents clients sont exclus des
traitements externes de preparation des donnees d'entrainement.

### Confidentialite : perimetre et limites

- Analyse : utiliser une instance Ollama locale et des modeles executes
  localement. La configuration effective et les flux reseau restent a auditer ;
  le prototype ne constitue pas une garantie d'absence de fuite.
- Entrainement : certains scripts de preparation peuvent utiliser Groq,
  exclusivement pour des donnees publiques ou synthetiques autorisees a cet usage.
  Une publication publique ne dispense pas de verifier les donnees personnelles
  residuelles et les conditions de reutilisation.
- `scripts/reecrire_faits.py` utilise Ollama par defaut. Groq exige les options
  `--fournisseur groq --confirmer-donnees-publiques-ou-synthetiques`.
  Cette confirmation est declarative : elle ne detecte pas les documents clients.
- Le script enregistre le fournisseur, le modele, l'empreinte du fichier source
  et la declaration dans chaque nouvelle sortie. Il ne verifie pas la pertinence
  juridique des exemples. Les anciennes sorties ne sont pas modifiees.

Les telechargements de corpus et de modeles sont distincts de l'analyse des
pieces. Ne pas placer de documents clients dans les entrees des scripts
d'entrainement, meme lors d'une execution locale.

---

## Etat actuel (2026-10-19)

Prototype avance. Non utilisable en production. L'etat est documente
dans docs/PROMESSES.md.

- 319 tests passent, 2 sont ignores dans l'environnement de verification.
- Pipeline complet : dossier PDF -> extraction -> analyse LLM ->
  verification -> rapport Markdown.
- Les citations choisissent un `article_id` candidat; code, numero et
  extrait sont reconstruits depuis le corpus local.
- Tracabilite : chaque citation indique le fichier et la page source.
- Verification : verdicts distincts pour numero absent, identifiant incoherent,
  article/version introuvable, statut source inconnu et extrait manquant ou
  different. Une version historique marquee `ABROGE` reste verifiable si sa
  periode couvre la date de reference.
- Etats de rapport : COMPLET, PARTIEL, ECHEC.

Ces resultats sont des tests logiciels. Ils ne valident pas la pertinence
juridique du moteur ni les labels synthetiques d'entrainement.

---

## Documentation

| Document | Contenu |
|---|---|
| docs/PROMESSES.md | Journal de bord ethique : ce qu'on promet, ce qu'on ne promet pas |
| docs/TESTS_JOURNAL.md | Toutes les commandes de test lancees, avec sorties brutes |
| docs/LLM_EVOLUTION.md | Evolution des prompts et du comportement du LLM |
| docs/JOURNAL.md | Chronologie du projet |
| [docs/VALIDATION_JURIDIQUE.md](docs/VALIDATION_JURIDIQUE.md) | Protocole de revue humaine, partitions et limites des mesures |

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
    export BEAUME_MODELE_OLLAMA=qwen2.5:7b-instruct

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
| LLM | Ollama (defaut `qwen-beaume-v1`, configurable avec `BEAUME_MODELE_OLLAMA`) |
| Recherche articles | SQLite FTS5 |
| Extraction PDF | PyMuPDF |
| Modeles Pydantic | Pydantic v2 |
| Tests | pytest |

---

## Licence

La licence du code n'est pas encore choisie par le porteur du projet.
Aucun fichier de licence du code n'est actuellement fourni. Les conditions
d'utilisation, de modification et de redistribution doivent etre clarifiees
avant diffusion sous une licence annoncee ou commercialisation.

Les licences des donnees et des modeles sont a inventorier separement, avec
leurs obligations d'attribution et de redistribution. L'abonnement envisage
dans la roadmap ne definit pas la licence du code. Le choix reste ouvert ;
cette section n'attribue pas une nouvelle licence au projet.
