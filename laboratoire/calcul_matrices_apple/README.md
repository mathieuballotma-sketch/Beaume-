# Calcul matriciel CPU et Metal

Cette expérience Swift réalise une multiplication de matrices en Float32 sur CPU ou avec un kernel Metal. Elle est indépendante du parcours principal et ne charge aucun modèle. Les compilateurs, les API, les pilotes et le matériel Apple ne sont pas développés par Beaume.

Sur un Mac disposant des outils de développement Apple :

```sh
cd laboratoire/calcul_matrices_apple
swiftc matrice_v2.swift -o /tmp/beaume_matrice_v2
/tmp/beaume_matrice_v2 --cpu
/tmp/beaume_matrice_v2 --metal
```

Le 15 novembre 2026, la compilation et le mode CPU ont réussi sur la copie publiée : huit exemples comparés à leurs résultats attendus et cinq entrées invalides refusées. Le GPU n'était pas accessible dans la session isolée de publication ; le mode Metal a renvoyé une erreur explicite et n'a pas été validé dans cette session.

Les exemples et tolérances présents dans le programme ne prouvent ni l'exactitude pour toutes les entrées, ni des performances comparatives, ni la prise en charge d'un LLM. Aucun test Windows, Linux ou Mac Intel n'est revendiqué.
