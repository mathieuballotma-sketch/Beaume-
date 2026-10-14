# Décisions techniques — Beaume

## 2026-10-08 — Arborescence
- Code dans `beaume/`, données dans `data/`.
- Chemins centralisés dans `beaume/config/paths.py`.
- Aucune donnée client dans git.

## 2026-10-08 — Logging
- Logger rotatif, 5 Mo × 5 fichiers, dans `data/logs/`.

## 2026-10-08 — Les 6 lois d'architecture
1. Dépendance descendante (couches L0->L5, jamais l'inverse)
2. Conservation de l'information (chaque transformation traçable)
3. Tiers exclu (machine à états fermée)
4. Inversion des dépendances (ports & adapters)
5. Composition fermée (une porte d'entrée par module)
6. Pureté au cœur, effets aux bords

## 2026-10-08 — Ontologie juridique
- Identifiant = LEGIARTI/LEGITEXT/JURITEXT + 12 chiffres
- Numéro humain (L. 1234-1) = alias, jamais identifiant
- Un article = plusieurs versions datées
- Une citation porte TOUJOURS une date de référence
- Immutabilité (frozen=True) sur les versions

## 2026-10-08 — Ports
- `Extracteur` : contrat unique pour tous les formats
- `RegistreExtracteurs` : ajout sans modification
- Aucun `if suffix == ".pdf"` dans le pipeline

## 2026-10-08 — Machine à états
- États : DEPOSE -> EXTRAIT -> DECOUPE -> INDEXE -> ANALYSE -> VERIFIE -> PUBLIE
- ECHEC accessible depuis n'importe quel état non terminal
- Transitions illégales = exception levée
- Historique horodaté conservé

## 2026-10-13 — HUD comme assistant, pas comme application
- L'avocat dépose son dossier dans la fenêtre HUD.
- Dès que l'analyse démarre, la fenêtre se replie dans un coin de l'écran.
- À chaque étape, le texte affiché décrit précisément ce que Beaume fait
  (ex : « Recherche des articles applicables… »).
- Signal discret : un point s'affiche au démarrage d'une action. Pas
  d'animation coûteuse en CPU/GPU.
- Objectif : habituer l'avocat à une **présence d'assistance**, pas à
  l'ouverture d'une application.
- Conséquence technique : le pipeline doit émettre des événements
  d'étape vers le HUD (aujourd'hui, il log dans un fichier). À prévoir
  une fois le noyau fiable.

## 2026-10-13 — Priorité fiabilité, puis vitesse
- Objectif : Beaume rend un résumé fiable d'un dossier client, avec
  articles cités, liens Legifrance et preuves vérifiables.
- **Fiabilité d'abord** : on ne cherche pas à être rapide tant que le
  taux de réussite n'est pas mesuré et acceptable.
- **Vitesse ensuite** : une fois la fiabilité mesurée, on optimise le
  temps là où il se perd réellement (mesure avant optimisation).
- Une analyse peut prendre plusieurs minutes si l'avocat voit ce qui se
  passe et comprend pourquoi. Un outil rapide mais faux est inutilisable.
- Conséquence : on ne peut pas dire « Beaume est fiable » sans un jeu
  de test et un chiffre. Le harnais de mesure est le prérequis de toute
  décision d'optimisation.

## 2026-10-13 — Idées d'architecture notées (à explorer, pas encore actées)

Ces idées sont enregistrées pour mémoire. Elles ne sont PAS des décisions
engagées. Chacune sera rouverte quand les conditions seront réunies.

### Calculateur d'adresse pour les numéros d'articles
- Un numéro d'article (`L. 1233-3`) est un vecteur structuré :
  nature / partie / livre / titre / chapitre / ordre.
- On peut calculer une adresse binaire unique (entier 64 bits) à partir
  de ce vecteur, sans recherche ni index textuel.
- Gain : accès direct O(1), index 20x plus compact (8 octets vs ~1000
  octets de texte).
- S'applique à LEGI (codes structurés). Pas à JURI/JORF (numérotation
  arbitraire).
- Limites : renumérotation de 2008 (table de correspondance requise),
  sous-articles `L. 1233-3-1`.
- Déclencheur : à partir de ~500 000 articles (aujourd'hui 25 767 —
  gain invisible).

### Bitmap de présence (0/1)
- Un bit par article possible : 1 = existe, 0 = abrogé/inexistant.
- Permet la détection instantanée de nouveauté (0→1) et d'abrogation
  (1→0).
- Taille : 99 articles d'un chapitre = 13 octets.
- Utile pour la veille quotidienne du corpus.

### Hash de contenu (détection de changement)
- Chaque version de texte a un hash (ex. xxHash64, 8 octets).
- Comparaison entre deux syncs = détection instantanée des articles
  modifiés.
- Combiné au bitmap, permet un différentiel complet du corpus.

### Découpage du corpus par zones
- 3 niveaux superposables : par nature (LEGI/JURI/JORF), par domaine
  (23 codes), par fréquence (hot/warm/cold).
- Objectif : ne charger que la zone pertinente au dossier.
- Un seul texte par article (pas de duplication), un index global, un
  routeur par code juridique.
- Déclencheur : à partir de 500 000+ articles.

### Moteur de calcul déterministe (calculatrice de règles)
- Au lieu que le LLM cherche les articles, un moteur de calcul applique
  des règles logiques aux faits du dossier.
- Le LLM ne sert plus qu'à la rédaction finale.
- Idée explorée : encoder 10 règles du licenciement économique dans un
  format standard, faire tourner le moteur sur 10 dossiers.
- Trois formes possibles : calculatrice pure (déterministe), arbre
  pondéré (score de certitude), hybride (structurel déterministe +
  interprétatif laissé à l'avocat).
- Change la nature du projet : application d'analyse → plateforme de
  calcul juridique. Décision à prendre à froid.
- Déclencheur : après stabilisation du corpus et du vérificateur.

### Mémoire quotidienne qui s'efface (veille corpus)
- Beaume regarde les nouveaux textes chaque jour.
- À la fin de la journée, il efface ce qu'il a vu et recommence.
- Avance sans reculer (pas d'accumulation).
- Source : dump DILA officiel (LEGI + JURI + JORF), mise à jour
  quotidienne par l'État. Pas de scraping Légifrance (interdit par CGU).
- Combiné au bitmap et au hash : détection de nouveauté et de
  changement automatique.

### Notification d'activité détectée
- Si Beaume voit un nouveau document dans un dossier, il demande
  l'autorisation avant de le lire.
- Message : « J'ai vu un nouveau fichier dans X, je peux l'analyser ?
  Voilà pourquoi. »
- Pas de lecture silencieuse. L'avocat reste maître.
- À arbitrer : surveillance continue (watchdog) ou surveillance limitée
  aux dossiers déjà déposés.

### Mise à jour sans friction
- L'avocat ne manipule rien.
- Beaume propose, l'avocat accepte (ou pas). Jamais l'inverse.
- Si une mise à jour existe, Beaume l'annonce, l'avocat choisit.

### Corpus : source DILA officielle
- Le dump DILA (echanges.dila.gouv.fr/OPENDATA) contient tout :
  LEGI (~500k articles), JORF (~2M textes), JURI (~500k décisions),
  KALI (~50k conventions), CNIL (~10k délibérations).
- Total ~3M documents.
- Gratuit, officiel, licence Etalab.
- Pas de scraping Légifrance (contraire aux CGU, pas nécessaire puisque
  DILA fournit tout).

## 2026-10-14 — Modèle de base + LoRA adapters par domaine
- **Un seul modèle de base** (Romulus ou équivalent, ~8 Go) partagé
  par tous les utilisateurs.
- **Un LoRA adapter par domaine** (~200 Mo chacun). Chaque adapter
  spécialise le modèle sur un domaine (travail, civil, consommation…).
- **Chargement à la demande** : le modèle de base reste en RAM, seul
  l'adapter actif est chargé (~1 s de bascule).
- **RAM active** : ~8,2 Go au lieu de 80 Go (10 adaptateurs séparés).
- Coût d'entraînement par adapter : 4-6 h sur GPU gratuit (Kaggle).

### Détection du domaine avant l'appel LLM
Le LLM ne devine jamais le domaine. Il le reçoit :
1. Le dossier est découpé en chunks (déjà fait).
2. Un détecteur analyse les chunks AVANT l'appel LLM.
3. Le détecteur choisit le domaine.
4. Le LoRA correspondant est chargé.
5. Le LLM est appelé avec l'adapter déjà actif.

### Trois niveaux de détection (progressif)
1. **Mots-clés** (dictionnaire `{mot: domaine}`) — 0 ms, 60-70 %.
   Premier niveau à implémenter.
2. **Classifieur léger** (250 Mo, embeddings) — 50 ms, 85-90 %.
   À construire si le niveau 1 ne suffit pas.
3. **Petit LLM** (qwen2.5:0.5b) — 1 s, 90-95 %.
   Réservé aux cas ambigus.

### Périmètre de démarrage
- **Licenciement économique uniquement** (Code du travail, ~200 articles).
- Une fois fiable (70-80 % de rappel), étendre à harcèlement, rupture
  conventionnelle, puis d'autres codes.
- Chaque domaine ajouté = 1 dataset + 1 entraînement + 1 adapter.

### Ce que ça change pour l'utilisateur
- À l'installation : l'avocat choisit ses domaines.
- Beaume télécharge le modèle de base + les adaptateurs sélectionnés.
- Chaque avocat a un Beaume personnalisé, mais tous partagent la base.
