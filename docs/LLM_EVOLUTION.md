# Evolution du LLM — Beaume

Ce document retrace les changements de prompt et de configuration du
LLM, avec les resultats observes. Il sert a comprendre pourquoi on
a fait ces choix, et a eviter de refaire les erreurs.

---

## Contexte

- Modele utilise : qwen2.5:7b-instruct (4,7 Go, local via Ollama).
- Tache : analyser un dossier client et produire un JSON structure
  avec citations d'articles de loi, sources (fichier + page).
- Contrainte : 100% local, aucune donnee client ne quitte la
  machine.

---

## Limites connues de Qwen 2.5 7B

Trois limites identifiees empiriquement :

1. Decrochage au-dela de ~750 tokens de prompt. Les instructions
   placees au debut sont ignorees.
2. Copie l'exemple donne au lieu de lire le dossier. Si un exemple
   JSON est present, Qwen reprend ses valeurs.
3. Reformule au lieu de copier. Quand on lui demande une citation
   litterale, il produit une paraphrase.

---

## Version 0 — Prompt initial (avant 2026-10-16)

### Configuration

- Prompt long (~2000 tokens).
- 10 regles au debut.
- Exemple JSON au milieu.
- Dossier a la fin.
- Pas de mode JSON natif.

### Resultat

    Dossier test_001 :
      Citations : 1
      Valides   : 0
      Rejetees  : 1 (texte_different)
      Source    : lettre_client.pdf (page 1)
      Extrait   : reformule

### Verdict

Tracabilite partielle (fichier + page corrects), mais extrait
reformule donc rejete par le verificateur.

---

## Version 1 — Prompt renforce (2026-10-16)

### Changement

Ajout de la regle COPIE LITTERALE + exemples interdits.

### Resultat

    Dossier test_001 :
      Citations : 1
      Valides   : 0
      Rejetees  : 1
      Source    : lettre_client.pdf (page ?)
      Extrait   : reformule

### Verdict

Regression. Le prompt plus long a degrade la tracabilite (page ?
au lieu de 1). Qwen se perd dans les instructions.

---

## Version 2 — Prompt court + JSON natif (2026-10-16)

### Changements

1. Prompt reduit a ~400 tokens.
2. Dossier AVANT les regles (correction du biais de position).
3. Exemple JSON retire (Qwen le recopiait).
4. Mode JSON natif Ollama active : format=SCHEMA_ANALYSE.
5. Schema JSON simplifie (sans $ref, anyOf, const).
6. Liste des fichiers du dossier injectee en tete.

### Structure du prompt

    [SYSTEM court : 5 regles]

    === LISTE DES FICHIERS DU DOSSIER ===
    [fichiers reels]

    === DOSSIER CLIENT ===
    [contenu avec en-tetes [nom.pdf, page X]]

    === ARTICLES DISPONIBLES ===
    [articles]

    === DATE DE REFERENCE ===
    [date]

    === REPONSE (JSON uniquement) ===

### Resultat dossier simple

    Dossier test_001 :
      Citations : 2
      Valides   : 2
      Rejetees  : 0
      Extrait   : litteral

### Resultat dossier multi-fichiers

    Dossier gros_001 :
      Citations : 3
      Valides   : 2
      Rejetees  : 1
      Fichiers  : conclusions.pdf (invente)

### Verdict

Premier run reussi sur dossier simple. Deux problemes restants :

1. Le LLM invente des noms de fichiers quand il ne sait pas.
2. Une citation rejetee (texte_different) sur le dossier
   multi-fichiers.

---

## Tableau comparatif

    Version | Prompt tokens | Mode JSON | Dossier avant regles | Exemple JSON | Citations valides
    --------|---------------|-----------|----------------------|--------------|------------------
    0       | 4090          | non       | non                  | oui          | 0
    1       | 2050          | non       | non                  | oui          | 0
    2       | 3577          | oui       | oui                  | non          | 2

Lecture : la version 2 gagne sur le seul critere qui compte
(citations valides). Les choix decisifs :

- Mode JSON natif (contraint la structure).
- Dossier avant les regles (biais de position corrige).
- Exemple JSON retire (evite la recopie).

---

## Configuration actuelle

### Modele

qwen2.5:7b-instruct

### Prompt (beaume/application/prompts.py)

- 5 regles, ~400 tokens.
- Ordre : system -> fichiers -> dossier -> articles -> date -> reponse.
- Pas d'exemple.

### Schema JSON (beaume/adapters/generateur_ollama.py)

- contexte (string, required).
- parties, demandes, problemes_juridiques (list of string).
- citations (list of objects, required).
  - Chaque citation a : code, numero, extrait, pages, fichier.
  - Tous required.
- Pas de $ref, anyOf, const.

---

## Prochaines pistes (non testees)

1. Validation post-traitement du nom de fichier. Si fichier n'est
   pas dans la liste reelle des fichiers du dossier, remplacer par
   vide et logger un warning.

2. Rendre fichier optionnel dans le schema. Forcer un nom de
   fichier incite a l'invention. Optionnel + validation cote code
   est plus sur.

3. Ajouter un exemple de sortie TRES different du dossier. Exemple
   sur un sujet (bail commercial) qui n'a rien a voir avec les
   dossiers testes (droit du travail). Ainsi Qwen ne peut pas
   recopier les valeurs.

4. Tester sur un modele plus gros (qwen2.5:14b ou 32b) si le Mac
   le supporte (24 Go RAM). Le 7B plafonne.

5. Boucle de validation iterative. Si le verificateur rejette une
   citation, redemander au LLM de la corriger. Deuxieme passe.

6. Few-shot dynamique. Prendre 1-2 exemples de paires (fait,
   article) des decisions annotees manuellement (a construire).

---

## Comment relancer une analyse et comparer

    cp data/out/dossier_test_001_analyse.md data/out/dossier_test_001_analyse_v2.md
    PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/dossier_test_001 2024-01-01
    diff data/out/dossier_test_001_analyse_v2.md data/out/dossier_test_001_analyse.md

Observer dans la sortie :

- Citations : X (Y valides, Z rejetees).
- Ligne Source dans le dossier : fichier.pdf (page(s) N).
- L'extrait propose est-il une copie litterale ?
