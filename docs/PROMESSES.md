# PROMESSES — Journal de bord éthique de Beaume

> Ce document n'est pas un contrat figé. C'est un journal de bord.
> Il décrit ce que Beaume promet **aujourd'hui**, ce qu'il ne promet
> pas encore, et ce qu'il vise à terme. Il évolue à chaque étape
> majeure du projet.

Dernière mise à jour : 2026-10-16
Version : 0.3
Statut : **Beaume n'est pas utilisable en production.**

---

## 0. État actuel — 2026-10-16

**Ce que Beaume fait aujourd'hui :**

- Lit les PDF natifs (pas les scans).
- Découpe le texte en chunks.
- Cherche des articles par FTS5 (mots-clés, pas sens).
- Envoie les chunks + articles candidats à un LLM local.
- Produit un résumé structuré en JSON.
- Vérifie que les articles cités existent et ne sont pas abrogés
  dans le corpus actuel (version 2025 uniquement).

**Ce que Beaume ne fait pas encore :**

- Lire les PDF scannés (30-40 % d'un dossier réel).
- Comprendre le sens d'une question juridique (top-1 à 9 % sur
  petit dataset, en cours d'évaluation sur 1118 paires).
- Tracer un fait à sa page d'origine.
- Signaler les analyses partielles.
- Distinguer un fait d'une prétention de partie.
- Vérifier la version historique d'un article (chantier en cours,
  voir 3.7).
- Fonctionner sur un dossier de 200 pages.

**Verdict :** Beaume est un prototype. Aucun avocat ne doit
l'utiliser sur un vrai dossier. Il produit des résultats
plausibles, pas des résultats fiables.

---

## 1. Règle de mise à jour

Ce document est mis à jour **à chaque étape majeure** :

- Quand une promesse devient mesurable → elle passe de "visée"
  à "promise".
- Quand une promesse mesurée échoue → elle est retirée ou
  révisée.
- Quand une nouvelle limite est identifiée → elle est ajoutée
  dans la section "Ce que Beaume ne promet pas".

**Toute mise à jour est un commit Git séparé.**

L'historique Git **est** l'historique des promesses.

---

## 2. Ce que Beaume promet aujourd'hui

**Section vide au 2026-10-16.**

Aucune promesse n'est encore tenable, car aucune n'est mesurée.
Ce n'est pas un échec. C'est le point de départ.

---

## 3. Ce que Beaume vise (promesses futures)

### Visée 1 — Aucune donnée client ne quitte la machine

**Mesure :** audit réseau sur 10 dossiers réels (tcpdump). Vérifier
qu'aucun paquet sortant ne contient de chaîne issue du dossier.

**Seuil cible :** 0 occurrence sur 10 dossiers.

**Statut :** non mesuré.

---

### Visée 2 — Aucun fait inventé

**Mesure :** sur 50 résumés, vérifier manuellement que chaque fait
est présent dans le texte source.

**Seuil cible :** < 0,1 % de faits non traçables.

**Chantier :** traçabilité page → fait (patch extracteur PDF +
propagation dans le chunker + rendu).

**Statut :** chantier non commencé.

---

### Visée 3 — Aucun article abrogé présenté comme valide

**Mesure :** sur 100 citations, vérifier que la version citée
correspond à la version en vigueur à la date de référence du
dossier.

**Seuil cible :** 0 article abrogé présenté comme VALIDE.

**Chantier :** propagation de la date de référence (fait le
2026-10-15), corpus avec versions historiques (en cours).

**Statut :** mécanisme partiel. Le corpus actuel ne contient
qu'une version par article. Un nouveau corpus est en cours
d'intégration (voir 3.7).

---

### Visée 4 — Les limites sont signalées

**Mesure :** sur 20 dossiers contenant des cas d'échec (PDF scanné,
domaine non couvert, réponse LLM cassée), vérifier que le rapport
signale l'échec.

**Seuil cible :** 100 % des cas d'échec signalés.

**Chantier :** ajouter `erreur: str | None` et
`fichiers_ignores: tuple[str, ...]` dans `Analyse`. Afficher l'état
dans le rendu Markdown.

**Statut :** chantier non commencé.

---

### Visée 5 — La provenance est vérifiable

**Mesure :** vérification automatique que chaque citation du
rapport contient code + numéro + version + lien.

**Seuil cible :** 100 % des citations complètes.

**Statut :** partiel. Les citations contiennent code + numéro.
Version et lien manquants.

---

### Visée 6 — Pertinence des articles

**Mesure :** Recall@5 sur un jeu de validation annoté (50
décisions, faits bruts + paraphrases).

**Seuil cible :** Recall@5 > 60 %.

**Statut :** chantier en cours. Premier essai mécanique le
2026-10-16 sur 1118 paires. Résultat à interpréter avec
prudence (15 faits de test seulement).

---

## 4. Ce que Beaume ne promet PAS

### 4.1 La pertinence juridique

Beaume trouve des articles **existants** et **en vigueur**. Il ne
garantit pas qu'ils sont **pertinents** pour les faits.

### 4.2 L'analyse des PDF scannés

Beaume ne lit pas les PDF scannés. Il les signale comme non lus.

### 4.3 Le conseil juridique

Beaume ne donne pas de conseil juridique. L'avocat reste seul
responsable.

### 4.4 La couverture de tous les domaines

Beaume couvre aujourd'hui 5 codes (travail, civil, sécurité
sociale, procédure civile, consommation). Les autres arriveront
progressivement.

### 4.5 La vitesse

Beaume ne promet pas d'être rapide. Il promet d'être **fiable**.

### 4.6 L'exhaustivité

Beaume ne peut pas garantir de tout lire d'un dossier. S'il
ignore un fichier, il doit le dire.

### 4.7 La version historique des articles

**État au 2026-10-16 :** Beaume vérifie les articles contre le
corpus actuel, qui ne contient **qu'une seule version par article**
(la version en vigueur en 2025).

**Conséquence :** pour un dossier de 2018, Beaume vérifie contre
la version 2025. Si l'article a été modifié entre 2018 et 2025,
la vérification peut être fausse.

**Chantier en cours :** intégration du dataset officiel
`AgentPublic/legi` (Etalab, 2 198 872 lignes, versions
historiques avec `start_date` / `end_date` / `status`).
Téléchargement terminé le 2026-10-16.

**Prochaines étapes :**
1. Construire un nouveau corpus SQLite `legi_full_v2.sqlite`
   avec les versions historiques (filtre sur 5 codes).
2. Adapter `DepotSQLite.trouver_par_id(article_id, date_reference)`
   pour chercher la version applicable à la date.
3. Reconstruire le dataset d'entraînement avec les bonnes versions.

**Effort estimé :** ~4 h.

**Tant que ce n'est pas fait :** chaque rapport doit mentionner
*"Vérifié contre le corpus 2025"* dans son en-tête.

---

## 5. Les états de sortie (à implémenter)

Tout rapport produit par Beaume aura un état explicite :

| État | Signification |
|---|---|
| `COMPLET` | Tous les fichiers lus, tous les articles vérifiés, aucune erreur. |
| `PARTIEL` | Au moins un fichier ignoré ou un article non vérifié. Le rapport liste les manques. |
| `ECHEC` | Aucun fichier exploitable, ou LLM a produit une réponse illisible. |

**Règle :** un rapport ne peut jamais être `COMPLET` si un seul
élément manque.

**Statut :** non implémenté.

---

## 6. Comment on vérifiera

**Tests automatisés (CI) :**
- Tests unitaires sur chaque promesse mesurable.
- Test d'intégration sur 5 dossiers de référence.
- Test réseau sur 1 dossier.

**Audit manuel :**
- 50 résumés relus par un juriste (quand Beaume sera utilisable).
- Publication des résultats dans `docs/AUDIT.md`.

**Test utilisateur :**
- Un avocat pilote testera Beaume sur 5 dossiers réels par mois.

---

## 7. Ce qu'on fera quand une promesse n'est pas tenue

**Étape 1 — Constat.** On écrit le chiffre exact.
**Étape 2 — Communication.** Correctif dans `docs/CORRECTIFS.md`.
**Étape 3 — Correction.** Patch + test de non-régression.
**Étape 4 — Retrait.** Pas de "bientôt". Pas de "en cours".

---

## 8. Ce qui n'est pas encore défini

- Seuils exacts de Recall@5, Recall@10.
- Mécanisme d'annotation des dossiers de validation.
- Format exact du rapport Markdown.
- Fréquence de l'audit.
- Qui fera l'annotation (rémunération, bénévolat).

---

## 9. Signatures

Ce document engage :
- Mathieu Bellot, fondateur.
- Toute personne qui contribue au code de Beaume.

---

*Document vivant. Version courante dans `docs/PROMESSES.md`.
Historique complet dans Git.*