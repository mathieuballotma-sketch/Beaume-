# 🗺️ ROADMAP BEAUME - Vision & Développement

Ce document regroupe les idées, l'architecture cible et les étapes de construction de Beaume. Il doit être mis à jour à chaque avancée majeure ou nouvelle idée validée.

## 🎯 1. Philosophie & Contraintes (Non négociables)
- **Analyse locale et confidentialité** : Objectif : traiter les dossiers sur la machine de l'avocat, avec Ollama local. Groq a seulement servi ponctuellement à préparer des données pendant le développement ; il ne fait pas partie de l'architecture produit ni du pipeline d'analyse. L'absence de fuite reste à vérifier par un audit de configuration et de flux. Voir le périmètre dans le [README](../README.md).
- **Frugalité** : Zéro coût d'infrastructure. Utilisation d'outils gratuits (Ollama, Kaggle, Python, SQLite) et du matériel existant (Mac M4 24Go).
- **Traçabilité stricte** : Le modèle ne doit jamais inventer de source. Chaque citation doit pointer vers un fichier, une page et un texte exact.
- **Transparence Radicale** : L'avocat doit savoir où va son argent. Pas de boîte noire financière.

## 🏗️ 2. Architecture Cible (Le schéma global)
- **Le Routeur / Chercheur (Embedder)** : Transforme les faits du dossier en vecteurs. Utilise un **Routage Hiérarchique** pour filtrer par code (Travail, Civil, etc.) et économiser la RAM. Voir l'idée détaillée en section 6.1.
- **Le Rédacteur (Petit LLM)** : Fine-tuné sur Kaggle (QLoRA). Rôle : Extraire les faits et remplir un schéma JSON strict à partir des articles fournis.
- **Le Vérificateur (Juge / Humain)** : Filtre de sécurité (LLM-as-a-judge + validation déterministe en Python + relecture par l'avocat).
- **Le Serveur de Licence (P2P Check)** : Un serveur ultra-léger qui gère uniquement les abonnements (Oui/Non), totalement déconnecté des données clients.

## 💳 3. Modèle Économique & Licence (Le Pacte de Confiance)

Les mécanismes ci-dessous sont des objectifs produit. La licence du code reste
à choisir par Mathieu ; un abonnement ne définit pas les droits sur le code.
Les licences des corpus et modèles doivent être recensées séparément.

- **Paiement Direct (P2P)** : L'avocat paie un abonnement abordable. Le serveur de licence valide le paiement sans jamais voir les dossiers.
- **Validation "Aveugle"** : Le Mac envoie juste un identifiant machine. Le serveur répond `{"status": "active"}`.
- **Période de Grâce (Offline)** : Licence valide 30 jours. Si l'avocat est hors-ligne (tribunal, panne), il a 10 jours supplémentaires de tolérance avant blocage de l'outil.
- **Transparence Financière (Dashboard "Open Startup")** : Un espace client (ou un site web public) où chaque avocat peut voir :
  - Les revenus globaux générés par Beaume.
  - Le salaire versé au créateur (toi).
  - Les investissements (frais de serveurs, matériel, etc.).
  - La répartition exacte des bénéfices.
- **Participation Citoyenne** : Les abonnés ont un droit de regard sur les évolutions.

## 📊 4. Boucle de Retour Utilisateur (Feedback Loop)
- **Sondages Intégrés** : Intégration d'un module de sondage dans l'application ou l'espace client pour voter sur les prochaines fonctionnalités (ex: "Préférez-vous qu'on ajoute le Code pénal ou la jurisprudence ?").
- **Boîte à Questions** : Un canal direct pour que les avocats posent des questions sur le développement, signalent des bugs ou proposent des ajouts.
- **Suivi Public (Roadmap Interactive)** : Un tableau de bord où les avocats voient l'avancement des fonctionnalités qu'ils ont demandées.

## 🚀 5. Les Phases de Développement

### Phase 1 : Consolidation du Socle Technique (En cours)
- [x] Correction du bug d'invention de fichiers (schéma JSON strict).
- [x] Ajout des Enums pour forcer le choix dans les listes.
- [x] Création du script de génération de dataset (Générateur).
- [x] Création du script de vérification (Juge automatique).
- [x] Premier Fine-Tuning sur Kaggle (Qwen 2.5 3B via Unsloth).
- [ ] **Export du modèle GGUF et test sur `dossier_gros_001`.**

### Phase 2 : La Recherche Sémantique & Le Routage (Prochaine étape)
- [ ] Mise en place d'une base de données vectorielle locale (ChromaDB, Qdrant ou FAISS).
- [ ] Entraînement du modèle d'Embedding (BGE-M3 ou CamemBERT) sur les paires `train_embedder.jsonl`.
- [ ] Implémentation de l'idée de **Routage Hiérarchique** (Filtrage par domaine avant la recherche vectorielle pour économiser la mémoire vive). Voir section 6.1 pour la version détaillée.
- [ ] Remplacement de la recherche SQLite FTS5 actuelle par la recherche hybride (Sparse + Dense).

### Phase 3 : Le Raisonnement Juridique (Moyen terme)
- [ ] **Intégration des Cours du Barreau** : Extraire la méthodologie (qualification des faits, problème de droit, conclusion) et la Lucie-7B) pour la rédaction finale.
- [ ] Ajout des décisions de justice (jurisprudence) dans la base de données.

### Phase 4 : Packaging, Business & Écosystème (Long terme)
- [ ] Création de l'interface utilisateur (Streamlit ou Tauri).
- [ ] Mise en place du serveur de licence et du système de paiement (Stripe/LemonSqueezy).
- [ ] Création du Dashboard de transparence financière.
- [ ] Déploiement de la boîte à idées et des sondages pour les avocats.
- [ ] Présentation du prototype aux réseaux (Open Law, AvoTech) et tests réels.
- [ ] Revue juridique suivant le [protocole](VALIDATION_JURIDIQUE.md), avec jeu de développement et test final séparés.

## 💡 6. Le Backlog (Boîte à idées techniques)

### 6.1 Routage par activation localisée (idée, non implémentée)
- **Intuition d'origine** : reconnaissance de formes → activation de zones spécialisées → vérification par rétroaction. Métaphore de la vision et du neurone, pas de la biologie. L'idée est de faire comme un système qui reconnaît une forme familière et active seulement les zones qui savent la traiter, au lieu de tout recalculer à chaque fois.
- **Problème actuel dans Beaume** : le retrieval cherche dans tout le corpus (1,75 M articles DILA, ou 25 767 en v1), puis filtre par date. Le bruit est mécanique. BE-LECO-002 en est l'illustration : L1233-2 et L1233-1 ne remontent pas dans le top 5 FTS5, noyés dans les articles hors sujet.
- **Ce qui existe déjà** :
  - RRF (Reciprocal Rank Fusion) dans `_enrichir_articles` : fusionne les classements de plusieurs chunks.
  - Filtre par `code` dans `rechercher_texte` : mais **après** le retrieval, pas avant.
  - Vérificateur (`VerificateurStandard`) : rejette les citations non conformes, mais **sans rétroaction** vers le retrieveur.
- **Ce qui manque** : un routeur explicite qui décide **où chercher** avant de chercher, et qui reçoit un signal de retour quand le vérificateur rejette une citation.
- **Comment on le testerait, dans l'ordre** :
  1. **Baseline mots-clés** (1 h) : un dictionnaire `SIGNATURES_CODES` à la main, un score par code, on garde les codes au-dessus d'un seuil. Mesurer la précision sur les 5 dossiers actuels. Si le routeur ne trouve pas `code_travail` sur les 5 dossiers, il ne sert à rien.
  2. **BGE-M3 sans réentraînement** (2 h) : encoder les descriptions de codes (titre + premiers articles) et le fait, calculer la similarité cosinus. Même mesure. BGE-M3 est déjà installé.
  3. **Petit classifieur 3B** (2–3 semaines) : seulement si 1 et 2 échouent. Réentraîner le 3B sur `(fait, code)` → `code_travail`. C'est là que le réentraînement devient pertinent.
- **Ce que ça ne résout pas** :
  - BE-LECO-002 (article absent du corpus) : le routeur ne crée pas d'articles.
  - La validation juridique : le routeur dit "code du travail à 87 %", pas "cet article s'applique juridiquement".
  - Le refus : un routeur peut se tromper avec assurance.
  - Le jeu de 5 dossiers : un routeur qui fait 5/5 sur 5 dossiers ne prouve rien sur 500.
- **Prérequis** : le mapping `LEGITEXT → CodeJuridique` du corpus DILA (en cours). Sans ce mapping, le routeur ne peut pas activer "code_travail" s'il ne sait pas que `LEGITEXT000006072050` = Code du travail.
- **Statut** : hypothèse. Ni implémentée, ni testée, ni validée. À mesurer sur un jeu élargi (20–30 dossiers) avant toute conclusion.

### 6.2 Autres idées
- **Gestion de la mémoire** : Quantification binaire (int8) des vecteurs pour réduire l'espace de stockage de 90%.
- **Format des données** : Passer des JSONL au format Parquet compressé.
