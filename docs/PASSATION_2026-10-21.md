# Passation — Judilibre / Beaume, 21 octobre 2026

**Portée :** chantier Judilibre, du diagnostic de la livraison ChatGPT à la
mesure du plafond de la source. Ne couvre pas l'entraînement, ni les
données clients, ni la coordination avec Claude sur le format commun.

**État local :** HEAD `05465dc`, branche `main`, dépôt public
`mathieuballotma-sketch/Beaume-`. Les corrections de ce chantier sont
dans `beaume_judi_diag/` (non versionné) et dans `beaume/` (versionné
mais non commité à ce stade).

---

## 1. En une page

**Ce qui est fait :** les défauts A, B, C, D du parser et du générateur
sont corrigés et figés par tests. Le résolveur strict
`DepotSQLite.resoudre_article` est implémenté, testé (22 tests) et
cohabite avec `trouver()` sans régression. Le mode API distingue
désormais succès / succès sans résultat / erreur de collecte. La chaîne
de données est stabilisée (identifiants déterministes, provenance
complète, articles positifs préservés).

**Ce qui est mesuré :** sur 100 décisions tirées au hasard
(`seed=42`) dans `cour_de_cassation`, le plafond de décisions
acceptées est **0** sur `legi_full_v2.sqlite` (5 codes) comme sur
`legi_full_v3.sqlite` (10 codes). Le chiffre 9/50 annoncé dans la
mesure de plafond initiale était un **artefact** d'une regex naïve
utilisée dans `mesure_plafond_50.py`, pas le vrai parser. Ce chiffre
ne doit plus être cité.

**Décision à prendre :** l'élargissement du corpus (option B) a été
testé et échoue. Deux options restent ouvertes : A (API PISTE ciblée,
pour sélectionner les décisions au lieu de les subir) et C (chercher
les citations d'articles dans le texte des décisions, pas seulement
dans le champ `visa`). Aucune n'est engagée.

**Ce qui n'est pas démontré :** le mode API n'a pas été testé contre
PISTE en live. `generer_contexte.py` n'a pas tourné en bout de chaîne
(pas d'Ollama dans cette session). Les 408 tests du prompt initial
n'ont pas été réexécutés — seuls les 19 tests de `beaume_judi_diag`
et les 17 + 22 de `beaume/` ont été exécutés.

---

## 2. Ce qui est corrigé

| Défaut | Description | Fichier | Test | Statut |
|---|---|---|---|---|
| A1 | Plage `455-458` rejetée | `resoudre_visa.py` | `test_a1` | vert |
| A2 | Disjonction `L1233-3 ou L1233-4` rejetée | `resoudre_visa.py` | `test_a2` | vert |
| B | Années isolées détectées (`rupture en 2019`) | `extraire_judilibre.py` | `test_b` | vert |
| C1 | Permutation valeur/libellé | `generer_contexte.py` | `test_c1` | vert |
| C2 | Négation inversée | `generer_contexte.py` | `test_c2` | vert |
| C3 | Déterminant inventé dans la fiche | `generer_contexte.py` | `test_c3` | vert |
| D | Sociétés distinctes (pseudonymes distincts) | `extraire_judilibre.py` | `test_d` | vert |
| E | Mode API : query obligatoire, distinction erreur/résultat | `extraire_judilibre.py` | `test_e1/e2/e3` | vert |
| F3 | `fait_id` déterministe (`sha256(decision_id)[:12]`) | `extraire_judilibre.py` | — | fait |
| F4 | `--revision` (HF) et `--corpus-local` (local) | `extraire_judilibre.py` | — | fait |
| F5 | Une ligne par décision, `articles_positifs` | `extraire_judilibre.py` | — | fait |
| F2 | Métadonnées préservées dans `generer_contexte.py` | `generer_contexte.py` | `_metadonnees_preservees` | vert |

**Résolveur strict :**

- `beaume/ports/resolveur_articles.py` (nouveau) — `StatutResolution`,
  `ResolutionArticle`, `ResolveurArticles` (Protocol séparé de
  `DepotArticles` pour ne pas casser les faux dépôts existants).
- `beaume/adapters/depot_sqlite.py` — ajout de `resoudre_article`,
  sans modification de `trouver()` ni de `Article.version_a()`.
- `tests/unit/test_resoudre_article.py` (nouveau, 22 tests).
- `tests/unit/test_depot_sqlite.py` — 17 tests existants toujours verts.

**Contrat dual de `resoudre_reference` :** accepte `ResolutionArticle`
(nouveau contrat Beaume) et `NS(unique=True, article_id=...)` (ancien
contrat ChatGPT), pour préserver les consommateurs existants. La
dualité disparaîtra quand tous les appelants seront migrés.

---

## 3. Ce qui est mesuré

### Décompte des 100 premières décisions

Sur les 100 premières décisions du fichier (les plus anciennes) :

```
 34  visa:visa_absent
 28  visa:code_absent_ou_multiple  (Loi, LOI)
 25  expose:erreur_parsing  (zones: None)
  9  visa:suffixe_non_supporte  (et suiv., al. N)
  4  visa:code_hors_corpus  (commerce)
  0  DECISION_ACCEPTEE
```

Aucun levier de parsing n'est possible sur cet échantillon sans violer
une règle qu'on s'est fixée (tolérer `et suiv.` reviendrait à
transformer une plage en article, ce qui est A1).

### Décompte sur 100 décisions aléatoires (`seed=42`)

Répartition par décennie : 4 / 9 / 30 / 27 / 21 / 9 pour 1970s → 2020s.
L'échantillon est temporellement équilibré.

Base v2 (5 codes) :

```
 58  visa:visa_absent
 10  visa:code_hors_corpus
  9  visa:code_absent_ou_multiple
  7  expose:erreur_parsing
  7  visa:suffixe_non_supporte
  3  visa:plage_ambigue
  2  expose:expose_absente
  2  resolution:donnees_incoherentes
  2  visa:numerotation_ambigue
  1  visa:numero_article_invalide
  0  DECISION_ACCEPTEE
```

Base v3 (10 codes, parser élargi) :

```
 58  visa:visa_absent
 10  visa:code_absent_ou_multiple
  8  expose:erreur_parsing
  7  visa:suffixe_non_supporte
  6  visa:numerotation_ambigue
  3  visa:plage_ambigue
  2  date:date_faits_ambigue
  2  expose:expose_absente
  2  resolution:donnees_incoherentes
  2  visa:numero_article_invalide
  1  visa:code_hors_corpus
  0  DECISION_ACCEPTEE
```

**Le patch du parser a bien converti 9 des 10 `code_hors_corpus` en
codes reconnus. Mais ces décisions bloquent plus loin** :
`numerotation_ambigue` (`1382 et suiv.`), `date_faits_ambigue`. Le
plafond est déplacé, pas supprimé.

### Conclusion de la mesure

Le plafond réel de `antoinejeannot/jurisprudence` × `cour_de_cassation`
× `legi_full_v*.sqlite` est **0 décision acceptée sur 100 tirées au
hasard**. Les 58 `visa_absent` et 8 `expose:erreur_parsing` (zones
absentes) sont des plafonds durs. Aucun correctif de parser ne les
franchit.

---

## 4. Ce qui reste ouvert

### Option A — API PISTE ciblée

**Principe :** au lieu de subir les décisions d'un dataset figé, utiliser
l'API `/search` de PISTE pour sélectionner les décisions qui contiennent
un visa exploitable, ou pour chercher par article cité.

**Argument pour :** la source Judilibre-HF ne fournit pas de matière
exploitable (58 % sans visa, 8 % sans expose). Une requête ciblée peut
constituer un lot 100 % exploitable en quelques minutes, sans changer
de contrat.

**Coût :** clé PISTE (`JUDILIBRE_API_KEY`), tests live, adaptation du
mode API (déjà partiellement fait, défaut E corrigé). Nouvelle
sélection : la question n'est plus « combien de décisions passent ? »
mais « combien de décisions puis-je obtenir ? ».

**Non testé :** le mode API n'a jamais été exercé contre PISTE en live.
Le code lève `ErreurCollecte` proprement en cas de clé manquante, mais
le contrat `/search` réel (paramètres, pagination, format de réponse)
n'a pas été confronté au serveur.

### Option C — Chercher les citations dans le texte

**Principe :** les décisions sans `visa` (58 %) citent souvent des
articles dans leurs motifs ou leurs moyens. Chercher les citations
dans le texte, pas seulement dans le champ structuré `visa`.

**Argument pour :** c'est la seule piste qui attaque frontalement les
58 % `visa_absent`. Un visa absent ne signifie pas une absence de
référence juridique — cela signifie que le champ `visa` n'est pas
rempli dans le dataset.

**Coût :** significatif. C'est une nouvelle chaîne (parsing de texte
libre, désambiguïsation, vérification), pas une correction. Il faut
définir un format de citation, un parseur, et un contrôle de
provenance distinct du visa.

**Non démontré :** personne n'a mesuré combien de citations on
trouverait dans les motifs. C'est un pari raisonnable mais non
instruit.

### Option B — Élargir le corpus (échouée)

Testée le 21 octobre 2026. `legi_full_v3.sqlite` (10 codes, 78 605
articles) a été construit en 1 901 s. Le parser a été élargi aux 5
nouveaux codes. Résultat : **0 décision acceptée sur 100**, gain nul
par rapport à v2. Le plafond a été déplacé (de `code_hors_corpus` vers
`numerotation_ambigue`, `date_faits_ambigue`), pas supprimé.

**Ne pas refaire.** Élargir à 23 codes prendrait 60–90 min pour un gain
marginal probablement inférieur. Les 58 % sans visa et 8 % sans
expose resteraient hors d'atteinte.

---

## 5. Procédure de reproduction

### Empreintes

| Fichier | SHA-256 |
|---|---|
| `legi_full_v2.sqlite` | `3e86c3931e8d6026904b85931701edecc93ab38c73eae35d1158ee75bdd37a30` |
| `legi_full_v3.sqlite` | `bbcf50b88613e4c298acf0bc096765e570b8dfd1b39466ed2c9495d981e7d5bc` |

### Tests unitaires

```
cd /Users/mathieubellot/Projets/beaume
python -m pytest -q tests/unit/test_depot_sqlite.py
python -m pytest -q tests/unit/test_resoudre_article.py

cd /Users/mathieubellot/Projets/beaume_judi_diag
PYTHONPATH=. python -m pytest -q tests/unit/
```

Attendus : 17, 22, 19 — tous verts.

### Décompte aléatoire (le chiffre de référence)

```
cd /Users/mathieubellot/Projets/beaume_judi_diag
PYTHONPATH=. python scripts/decompte_aleatoire.py \
  --base /Users/mathieubellot/Projets/beaume/data/vector/legi_full_v3.sqlite \
  --n 100 --seed 42
```

### Lot 100 inspectable

```
cd /Users/mathieubellot/Projets/beaume_judi_diag
PYTHONPATH=. python scripts/extraire_judilibre.py \
  --source local --n 100 \
  --sortie /Users/mathieubellot/Projets/beaume/data/jurisprudence/lot_100.jsonl \
  --rapport /Users/mathieubellot/Projets/beaume/data/jurisprudence/lot_100_rapport.json \
  --manifest /Users/mathieubellot/Projets/beaume/data/jurisprudence/lot_100_manifest.jsonl
```

---

## 6. Ce qui n'est pas démontré

- **Live PISTE** : jamais testé. Le mode API lève `ErreurCollecte`
  proprement en cas de clé manquante, mais le contrat `/search` réel
  reste à confronter.
- **`generer_contexte.py` en bout de chaîne** : pas exécuté (Ollama
  non disponible dans cette session). La préservation des métadonnées
  est testée isolément, pas la génération complète.
- **Heuristiques A–D** : testées sur les cas du prompt, pas sur un
  échantillon large. `_contient_negation` ne couvre ni `sans`, ni les
  doubles négations, ni les formes passives. `_ancrage_valeur` ne juge
  que les valeurs à ancrage local non ambigu.
- **Les 408 tests du prompt initial** : non réexécutés. Seuls les
  19 + 17 + 22 tests des fichiers concernés ont été lancés.
- **`resolution:donnees_incoherentes` (2 cas)** : c'est
  `resoudre_reference` qui convertit le statut Beaume
  `donnees_incoherentes` en `VisaInvalide`. Sémantiquement faux — c'est
  un problème d'entrée, pas de visa. À corriger si le chantier reprend.
- **`visa:numero_article_invalide` (2 cas)** : `normaliser_numero`
  refuse des numéros qui passent `NUM_RE`. Cas non documentés, non
  corrigés.

---

## 7. Fichiers concernés

### `beaume/` (dépôt versionné)

- `beaume/ports/resolveur_articles.py` (nouveau)
- `beaume/adapters/depot_sqlite.py` (modifié : +`resoudre_article`)
- `tests/unit/test_resoudre_article.py` (nouveau, 22 tests)

### `beaume_judi_diag/` (non versionné)

Scripts :
- `scripts/resoudre_visa.py` (corrigé A, élargi aux 10 codes)
- `scripts/extraire_judilibre.py` (corrigé B, D, E, F2–F5)
- `scripts/generer_contexte.py` (corrigé C, F2)
- `scripts/mesure_plafond_50.py` (diagnostic, regex naïve — ne plus utiliser pour un chiffre)
- `scripts/mesure_local_50.py` (diagnostic, seed 42)
- `scripts/diagnostic_10.py` (diagnostic pas-à-pas)
- `scripts/decompte_100.py` (100 premières décisions)
- `scripts/decompte_aleatoire.py` (100 aléatoires, base paramétrable)

Tests :
- `tests/unit/test_defauts_a_d.py` (7 tests, verts après correction)
- `tests/unit/test_resoudre_visa.py` (livré ChatGPT, 5 tests, verts)
- `tests/unit/test_judilibre_gardes.py` (livré ChatGPT, 7 tests, verts)

Documentation :
- `JUDILIBRE_SCHEMA.md` (livré ChatGPT)
- `PASSATION_2026-10-21.md` (ce document)

### Bases

- `data/vector/legi_full_v2.sqlite` (275 Mo, 5 codes, 43 794 articles)
- `data/vector/legi_full_v3.sqlite` (537 Mo, 10 codes, 78 605 articles — non adoptée)

### Corpus

- `data/legal/jurisprudence/cour_de_cassation/` (Arrow, 553 075 décisions, 5 Go)