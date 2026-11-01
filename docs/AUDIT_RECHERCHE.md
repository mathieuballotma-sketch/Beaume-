# Recherche juridique : résultats et limites

## Résultats historiques

Une expérience documentée du 20 octobre 2026 portait sur cinq dossiers
synthétiques et le corpus `legi_full_v2.sqlite` : 43 794 familles d’articles,
92 767 versions. Modèle annoncé : `qwen2.5:7b-instruct` ; dix candidats maximum.
Empreinte historique du corpus :
`3e86c3931e8d6026904b85931701edecc93ab38c73eae35d1158ee75bdd37a30`.

Quatre dossiers aux annotations provisoires obtenaient 4 références attendues
retrouvées sur 4. Le cinquième dossier avait deux références attendues contestées,
non retrouvées. Le total brut était donc 4/6 ; la mesure excluant le dossier
contesté était 4/4. **Aucun de ces scores ne démontre une fiabilité générale.**
Les labels n’ont pas reçu de validation juridique indépendante et les résultats
bruts complets de cette expérience ne sont pas distribués dans ce dépôt.
Ce résumé conserve les limites et l’échec ; il ne constitue pas une nouvelle mesure.

## Reproduire une mesure

- `scripts/bench_recherche.py` : recherche sur requêtes factuelles ;
- `scripts/bench_qualite.py` : parcours avec modèle et vérification ;
- `beaume/bench/dossiers_test.json` : petit jeu exploratoire, pas un jeu de certification.

Lire `--help` pour les options et fournir explicitement corpus, modèle et sortie.
Conserver les empreintes, les candidats retrouvés, les réponses et les rejets.
Une recherche du texte d’un article contre lui-même mesure l’indexation, pas la
recherche juridique à partir des faits.

## Méthode attendue

Distinguer : présence de l’article attendu dans les candidats, sélection par le
modèle, conformité de la citation au corpus et pertinence juridique.
Comparer les systèmes sur les mêmes entrées. Regrouper les variantes et affaires
liées dans une même partition. Rapporter les cas contestés séparément.

Recall@K et MRR nécessitent des références adaptées ; la précision ne peut pas
être déduite d’une liste positive non exhaustive. Mesurer aussi les sorties
invalides et les réponses non étayées lorsque l’information manque.
