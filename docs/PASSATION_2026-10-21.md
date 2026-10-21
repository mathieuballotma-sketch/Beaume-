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

**Ce qui est mesuré :**

- Sur 100 décisions tirées au hasard (`seed=42`) dans
  `cour_de_cassation`, le plafond par **visa structuré** est **1/100**
  sur `legi_full_v3.sqlite` (10 codes), après correction du bug de
  contrat `resoudre_reference` → `resoudre_article`. Le chiffre 9/50
  de la mesure initiale était un **artefact** d'une regex naïve, pas
  le vrai parser. Ce chiffre ne doit plus être cité.
- Le plafond par **citations dans le texte** (chaîne C) est
  **50/100** sur le même tirage. 234 citations candidates, non
  qualifiées.
- L'élargissement du corpus de 5 à 10 codes (option B) a été testé
  et échoue : 0 gain sur le plafond visa. Ne pas refaire.

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

python -m pytest -q tests/unit/test_depot_sqlite.py
python -m pytest -q tests/unit/test_resoudre_article.py

_judi_diag
PYTHONPATH=. python -m pytest -q tests/unit/
```

Attendus : 17, 22, 19 — tous verts.

### Décompte aléatoire (le chiffre de référence)

```
_judi_diag
PYTHONPATH=. python scripts/decompte_aleatoire.py \
  --base /Users/mathieubellot/Projets/beaume/data/vector/legi_full_v3.sqlite \
  --n 100 --seed 42
```

### Lot 100 inspectable

```
_judi_diag
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

---

## 8. Addendum 2026-10-21 — chiffres post-fix et chaîne C

Cette section complète les sections 1 et 3 avec les résultats obtenus
après le commit `350ee17` (acceptation de `str` dans
`resoudre_article`). Les chiffres ci-dessous prévalent sur ceux des
sections précédentes.

### Décompte aléatoire v3 après correction du contrat

Répartition des 100 décisions tirées au hasard (`seed=42`) :

- 58 `visa:visa_absent`
- 10 `visa:code_absent_ou_multiple`
- 8 `expose:erreur_parsing`
- 7 `visa:suffixe_non_supporte`
- 6 `visa:numerotation_ambigue`
- 3 `visa:plage_ambigue`
- 2 `date:date_faits_ambigue`
- 2 `expose:expose_absente`
- 2 `visa:numero_article_invalide`
- 1 `DECISION_ACCEPTEE`
- 1 `visa:code_hors_corpus`

**1/100 sur le visa seul.** Les 2 `resolution:donnees_incoherentes` de
la mesure précédente sont devenus une décision acceptée (index
283060). Chiffre honnête, cohérent avec l'ordre de grandeur attendu.

### Chaîne C — citations dans le texte libre

Le bug de contrat entre `resoudre_reference` (chaîne) et
`DepotSQLite.resoudre_article` (enum) a été corrigé dans `350ee17`.
Avant correction, toute résolution par citation échouait sur
`DONNEES_INCOHERENTES` (108/108 sur la mesure C).

Après correction, deux lots produits :

- **Lot 100 séquentiel** (les 100 premières décisions, 1899-1915) :
  26 acceptées, 32 citations candidates. Artefact historique.
- **Lot 100 aléatoire** (`--shuffle --seed 42`) : **50 acceptées**,
  234 citations candidates. Distribution : 4/11/12/19/4 pour
  1980s→2020s. 23/50 sont post-2010.

Taux cohérent avec `mesure_c_resolution.py` (35/35 échecs visa =
51 %). **Ce que C ne produit pas :** des labels. 234 citations
candidates ne sont pas 234 labels. La qualification reste à faire.

### Qualification — non faite

Le lot aléatoire contient 234 citations sur 50 décisions ; aucune
n'est qualifiée comme décisive. `date_resolution = date_decision`
(pas la date des faits) est une approximation documentée.

Trois pistes possibles :

1. **Échantillon manuel** : 10 décisions post-2010, lecture des
   motifs, décision « décisif / incident / incertain ».
2. **Heuristique documentée** : par exemple « première citation des
   motifs », avec statut `citation_heuristique_faible`. Fragile.
3. **Report** : la chaîne C est stable, la qualification peut
   attendre un prochain chantier.

### Fichiers ajoutés depuis la section 7

Scripts :

- `scripts/extraire_citations.py` (nouveau, 437 lignes : extraction C)
- `scripts/mesure_c_potentiel.py` (diagnostic C, regex naïve)
- `scripts/mesure_c_resolution.py` (diagnostic C, résolution réelle)

Lots produits :

- `data/jurisprudence/lot_100.jsonl` (vide : 0 ligne)
- `data/jurisprudence/citations_candidates.jsonl` (26 lignes,
  100 premières décisions, artefact historique)
- `data/jurisprudence/citations_candidates_random.jsonl` (50 lignes,
  234 citations, tirage aléatoire)

---

## 9. Addendum — mesure des visas textuels (2026-10-21)

Cette section documente la mesure A proposée après la pré-revue IA.
Elle répond à la question : « la chaîne C rate-t-elle des visas
présents dans le texte mais absents des candidats ? »

### Méthode

Script `mesure_visas.py` (nouveau). Sur les 10 décisions post-2010 de
l'échantillon (tirage `--shuffle --seed 42`), il cherche les patterns
de visa — `Vu l'article X`, `Vu les articles X et Y`, `aux termes de
l'article X`, `sur le fondement de l'article X` — avec une regex
large. Chaque fragment est passé à `parser_reference` puis
`resoudre_reference`, et comparé aux candidats existants de
`citations_candidates_random.jsonl` au niveau `(code, numero)`.

### Résultats

Première mesure : 99 fragments, 31 parsés, 31 résolus, 0 nouveau.
Un diagnostic (`diagnostic_visas.py`) a montré que 66 fragments
étaient rejetés en `code_absent_ou_multiple` : la regex tronquait
`code de procédure civile` en `code de`. Le parser ne reconnaissait
pas le code, donc rejetait le visa.

Après correction de la regex (codes complets, alinéas tolérés) :
90 fragments, 75 parsés, 74 résolus, **0 nouveau**.

### Interprétation — visa vs moyen

Le `0` ne contredit pas la pré-revue IA. Il répond à une autre
question. La pré-revue IA identifie des **rôles** manquants : dans
C301029, « Vu l'article 783, alinéa 1er, du code de procédure
civile » au début de l'arrêt (rôle : visa de cassation). Le
`(code_procedure_civile, 783)` est déjà dans les candidats, mais à
un autre offset (dans le moyen).

Autrement dit :

- **Au niveau article** : la chaîne C capture tous les articles,
  y compris ceux cités en visa.
- **Au niveau rôle** : elle ne distingue pas visa et moyen. Tous
  les candidats ont la même étiquette `citation_candidate`, sans
  indication de leur fonction dans l'arrêt.

### Décision

**Pas de construction d'une chaîne « visas textuels » séparée.**
Ajouter l'annotation de rôle « visa » (identifié par `Vu l'article X`
en début d'arrêt) est possible, mais n'apporte aucun article
nouveau. C'est une annotation sémantique, pas une extension du
plafond.

L'annotation de rôle est reportée à une revue humaine, conformément
à la recommandation de la pré-revue IA : « deux annotations séparées
— rôle et pertinence — à réaliser avec le relecteur humain ».

### Limites

- **Échantillon de 10 décisions** (post-2010, tirage aléatoire). Non
  représentatif de l'ensemble du corpus.
- **Regex de visa approximatives.** Les patterns `Vu l'article X` et
  variantes ne couvrent pas toutes les formes possibles. Certains
  visas peuvent être manqués si la formulation est inhabituelle.
- **Faux positifs possibles.** Un `Vu l'article X` dans un moyen
  (pas dans le visa) est capturé comme visa. Le script ne distingue
  pas la position dans l'arrêt.
- **Code implicite.** Certains visas ne citent pas le code (« Vu
  l'article 1382 »). Ces formes ne sont pas résolubles par la
  chaîne actuelle et ne sont pas dans le décompte.

### Fichiers ajoutés

- `scripts/mesure_visas.py` (diagnostic, post-patch regex)
- `scripts/diagnostic_visas.py` (diagnostic des motifs de rejet)

---

## 10. Addendum — vigueur des citations en 2026 (2026-10-21)

Cette section mesure : « la version citée est-elle encore en vigueur
le 21 octobre 2026 ? » Ce n'est PAS la même question que « la
résolution est-elle correcte à la date des faits ? ».

### Chiffres bruts

Sur les 234 citations du lot aléatoire :
- 234 articles famille existent dans `legi_full_v3`
- 226 ont une version applicable en 2026 (8 non, articles abrogés sans remplacement)
- 71 pointent vers la version encore en vigueur en 2026 (30,3 %)
- 163 pointent vers une version modifiée depuis

Distribution par décennie de la décision :

| Décennie | Vigueur 2026 | Total | % |
|---|---:|---:|---:|
| 1980s | 1 | 7 | 14 % |
| 1990s | 1 | 19 | 5 % |
| 2000s | 3 | 21 | 14 % |
| 2010s | 59 | 177 | 33 % |
| 2020s | 7 | 10 | 70 % |

### Pourquoi ce n'est pas un défaut de la chaîne C

Beaume résout les citations à la **date de la décision** (et non à
la date d'aujourd'hui). Un arrêt de 1990 qui cite le L122-14-3 tel
qu'il existait en 1990 est correctement résolu à cette date. La
version citée a changé depuis (renumérotation du Code du travail en
2008), mais c'est un fait historique, pas une erreur de résolution.

Autrement dit : les 234 citations sont correctes pour leur date. La
question « sont-elles encore valides en 2026 » est une autre
question, qui dépend de l'usage.

### Deux usages, deux conclusions

**Usage 1 — entraînement sur le droit applicable à la date des faits.**
C'est l'usage actuel de Beaume (le pipeline vérifie
`version_a(date)`). Les 234 citations sont utilisables. Le taux de
vigueur en 2026 n'est pas pertinent.

**Usage 2 — modèle qui répond sur le droit actuel.** Les 234
citations se réduisent à :
- 71 directement utilisables (30,3 %)
- 7 seulement si on se limite aux décisions 2020s (3 % du corpus)

**Le corpus est trop mince en décisions 2020s** pour un entraînement
moderne sur le droit actuel. 10 décisions sur 100 dans le tirage
aléatoire, soit 7 citations valides. Ce n'est pas exploitable en
volume.

### Décision

**Pas de filtre de vigueur ajouté à la chaîne C.** La résolution à
la date de décision est le comportement voulu. Si l'objectif devient
de citer le droit actuel, un filtre explicite `date_decision >= 2020`
sera nécessaire, avec la conscience qu'il ne produit que 7 citations
sur 234.

### Fichiers ajoutés

- `scripts/mesure_vigueur.py` (mesure globale)
- `scripts/mesure_vigueur_par_decennie.py` (mesure par décennie)
