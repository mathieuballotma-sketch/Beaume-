# État du projet — 1 novembre 2026

Beaume est un prototype. Aucun résultat publié ne démontre aujourd’hui son
aptitude à l’analyse autonome de dossiers professionnels.

| Élément | État et limite |
| --- | --- |
| PDF → analyse → vérification → rapport | Implémenté ; l’analyse réelle exige corpus et modèle |
| Démonstration autonome | Parcours technique avec corpus et réponse fictifs |
| Recherche d’articles | FTS5 et références explicites ; généralisation non démontrée |
| Versions historiques | Résolveur et préparation DILA présents ; qualité dépend du corpus chargé |
| Sources documentaires | Contrôles de fichier/page ; soutien sémantique non garanti |
| Contrats de scénarios | Expérimentaux ; validation logicielle, pas juridique |
| PDF scannés | OCR non intégré au pipeline nominal |
| Performance et confidentialité en cabinet | À mesurer sur configuration définie |

Les états COMPLET/PARTIEL/ECHEC décrivent le traitement logiciel. Ils ne
certifient pas une analyse exhaustive ou juridiquement correcte.

Les deux catégories d’évaluation restent distinctes : tests déterministes du code
et mesures de pertinence sur exemples indépendants. Aucun compteur de tests ne
remplace une revue métier. Voir [tests](TESTS.md) et [recherche](AUDIT_RECHERCHE.md).
