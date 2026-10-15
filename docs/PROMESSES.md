# PROMESSES — Journal de bord éthique de Beaume

> Ce document n'est pas un contrat figé. C'est un journal de bord.
> Il décrit ce que Beaume promet **aujourd'hui**, ce qu'il ne promet
> pas encore, et ce qu'il vise à terme. Il évolue à chaque étape
> majeure du projet.

Dernière mise à jour : 2026-10-15
Version : 0.2 (brouillon)
Statut : **Beaume n'est pas utilisable en production.**

---

## 0. État actuel — 2026-10-15

**Ce que Beaume fait aujourd'hui :**

- Lit les PDF natifs (pas les scans).
- Découpe le texte en chunks.
- Cherche des articles par FTS5 (mots-clés, pas sens).
- Envoie les chunks + articles candidats à un LLM local.
- Produit un résumé structuré en JSON.
- Vérifie que les articles cités existent et ne sont pas abrogés.

**Ce que Beaume ne fait pas encore :**

- Lire les PDF scannés (30-40 % d'un dossier réel).
- Comprendre le sens d'une question juridique (top-1 à 9 %).
- Tracer un fait à sa page d'origine.
- Signaler les analyses partielles.
- Distinguer un fait d'une prétention de partie.
- Fonctionner sur un dossier de 200 pages.

**Verdict :** Beaume est un prototype. Aucun avocat ne doit
l'utiliser sur un vrai dossier. Il produit des résultats
plausibles, pas des résultats fiables.

---

## 1. Règle de mise à jour

Ce document est mis à jour **à chaque étape majeure**, c'est-à-dire :

- Quand une promesse devient mesurable → elle passe de "visée"
  à "promise".
- Quand une promesse mesurée échoue → elle est retirée ou
  révisée.
- Quand une nouvelle limite est identifiée → elle est ajoutée
  dans la section "Ce que Beaume ne promet pas".

**Toute mise à jour est un commit Git séparé**, avec un message
du type : `docs(promesses): v0.3 — ajout promesse X, retrait Y`.

L'historique Git **est** l'historique des promesses.

---

## 2. Ce que Beaume promet aujourd'hui

**Section vide au 2026-10-15.**

Aucune promesse n'est encore tenable, car aucune n'est mesurée.
Ce n'est pas un échec. C'est le point de départ.

Les promesses listées ci-dessous sont **visées**. Elles
deviendront des promesses quand on aura :

1. Un mécanisme de mesure.
2. Un seuil défini.
3. Une première mesure.

---

## 3. Ce que Beaume vise (promesses futures)

Chaque promesse visée est associée à :
- une **mesure** (comment on la vérifiera),
- un **seuil cible** (à partir de quand on la promettra),
- un **chantier** (quel travail technique est nécessaire).

### Visée 1 — Aucune donnée client ne quitte la machine

**Mesure :** audit réseau sur 10 dossiers réels (tcpdump). Vérifier
qu'aucun paquet sortant ne contient de chaîne issue du dossier.

**Seuil cible :** 0 occurrence sur 10 dossiers.

**Chantier :** tracer tous les appels réseau, documenter chaque
appel dans `docs/RESEAU.md`.

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

**Mesure :** sur 100 citations, vérifier contre LEGI que la version
citée correspond à la version en vigueur à la date de référence.

**Seuil cible :** 0 article abrogé présenté comme VALIDE.

**Chantier :** propagée la date de référence (fait le 2026-10-15),
ajouter un test de non-régression.

**Statut :** mécanisme partiel. Bug de date corrigé le 2026-10-15.

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

**Chantier :** patch du rendu Markdown.

**Statut :** partiel. Les citations contiennent code + numéro.
Version et lien manquants.

---

### Visée 6 — Pertinence des articles

**Mesure :** rappel@5 sur un jeu de validation annoté (30+ décisions).

**Seuil cible :** rappel@5 > 60 %.

**Chantier :** entraînement embedding (chantier en cours), jeu de
validation, mesures honnêtes.

**Statut :** chantier en cours. Top-1 actuel : 9 % sur 142 candidats
(non représentatif).

---

## 4. Ce que Beaume ne promet PAS

### 4.1 La pertinence juridique

Beaume trouve des articles **existants** et **en vigueur**. Il ne
garantit pas qu'ils sont **pertinents** pour les faits. C'est
l'avocat qui juge.

### 4.2 L'analyse des PDF scannés

Beaume ne lit pas les PDF scannés. Il les signale comme non lus.

### 4.3 Le conseil juridique

Beaume ne donne pas de conseil juridique. Il produit une analyse
de dossier. L'avocat reste seul responsable.

### 4.4 La couverture de tous les domaines

Beaume couvre aujourd'hui le droit du travail (licenciement
économique) partiellement. Les autres domaines arriveront
progressivement.

### 4.5 La vitesse

Beaume ne promet pas d'être rapide. Il promet d'être **fiable**.
Si l'analyse prend 5 minutes, c'est acceptable.

### 4.6 L'exhaustivité

Beaume ne lit peut-être pas toutes les pièces d'un dossier. S'il
en ignore, il doit le dire. Mais il ne peut pas garantir de tout
lire.

---

## 5. Les états de sortie (à implémenter)

Tout rapport produit par Beaume aura un état explicite :

| État | Signification |
|---|---|
| `COMPLET` | Tous les fichiers lus, tous les articles vérifiés, aucune erreur. |
| `PARTIEL` | Au moins un fichier ignoré ou un article non vérifié. Le rapport liste les manques. |
| `ECHEC` | Aucun fichier exploitable, ou LLM a produit une réponse illisible. Aucun résumé. |

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
- Quand Beaume sera utilisable : 50 résumés relus par un juriste.
- Publication des résultats (même mauvais) dans `docs/AUDIT.md`.

**Test utilisateur :**
- Un avocat pilote testera Beaume sur 5 dossiers réels par mois.
- Retour documenté dans `docs/PILOTE.md`.

---

## 7. Ce qu'on fera quand une promesse n'est pas tenue

**Étape 1 — Constat.** On écrit le chiffre exact. Sans relativiser.

**Étape 2 — Communication.** Si la promesse a été communiquée,
on publie un correctif dans `docs/CORRECTIFS.md`.

**Étape 3 — Correction.** On patche. On ajoute un test de
non-régression.

**Étape 4 — Retrait.** Tant que la promesse n'est pas tenue, elle
est retirée de la communication. Pas de "bientôt", pas de "en
cours de correction".

---

## 8. Ce qui n'est pas encore défini

- Seuils exacts de rappel@5, rappel@10.
- Mécanisme d'annotation des dossiers de validation.
- Format exact du rapport Markdown.
- Fréquence de l'audit.
- Qui fera l'annotation (rémunération, bénévolat).

Ces points seront tranchés dans les prochaines versions.

---

## 9. Signatures

Ce document engage :
- Mathieu Bellot, fondateur.
- Toute personne qui contribue au code de Beaume.

Toute contribution qui contredit une ligne de ce document doit
être discutée et documentée avant d'être mergée.

---

*Document vivant. Version courante dans `docs/PROMESSES.md`.
Historique complet dans Git.*