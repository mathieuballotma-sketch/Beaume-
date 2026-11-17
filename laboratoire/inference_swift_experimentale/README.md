# Premières briques d'inférence Swift — laboratoire

Cette publication présente des **sources expérimentales**, séparées du produit
Beaume. Leur objectif est d'étudier comment effectuer nos propres opérations
d'inférence sur Apple Silicon. Elles n'établissent ni la fiabilité du produit,
ni une compatibilité générale avec les modèles ou les ordinateurs.

## Contenu

Les fichiers de `sources/` sont copiés de l'étape F du laboratoire local :

- `gguf_fn.swift` : lecture expérimentale des métadonnées et tenseurs GGUF ;
- `deq_q4k_fn.swift`, `deq_q6k_fn.swift` et `matvec_quantifie.swift` :
  déquantification et produits matrice-vecteur par blocs ;
- `primitives_couche.swift` : normalisation, rotation, softmax et opérations
  utilisées par les couches ;
- `forward.swift`, `forward_kv.swift` et `helpers.swift` : parcours expérimental
  de 28 couches pour une configuration spécifique de Qwen2, avec et sans
  cache KV.

Le code appelle les API et le compilateur Apple ; ceux-ci ne sont pas des
composants développés par Beaume. Les chemins de modèle personnels, les
binaires, poids et données ne sont pas publiés ici. Les sources sont partagées
pour lecture et expérimentation, pas comme bibliothèque prête à être intégrée.
Les formats et dimensions sont spécifiques ; le lecteur et les calculs ne sont
pas durcis pour des fichiers malformés ou non fiables. **Ne pas utiliser de
données de clients.**

## Compilation et petit contrôle synthétique

Sur macOS avec Swift installé :

```sh
swiftc -O sources/*.swift verification/main.swift -o /tmp/beaume_verif_inference
/tmp/beaume_verif_inference
```

Le contrôle vérifie quelques primitives sur des entrées synthétiques et ne
charge aucun modèle. Il ne valide ni GGUF, ni les déquantifications, ni les
28 couches, ni une génération, ni la sécurité du lecteur. Il n'y a pas de
commande d'inférence complète reproductible livrée dans cette sélection.

## Expériences historiques rapportées

Les éléments suivants résument des comptes rendus locaux ; ils n'ont pas tous
été rejoués pour cette publication :

- Étape F : sur un prompt et cinq tokens générés, deux implémentations avec et
  sans cache KV ont produit les mêmes tokens. Cette mesure seule ne prouve pas
  l'égalité des logits complets ou la fidélité au modèle.
- Étape H : une variante expérimentale ultérieure `no-ptr`, **non incluse dans
  ces sources F**, a été comparée sur une courte séquence ; un gain de temps
  d'environ 26 % est rapporté sur cette machine et ce cas. Pas de conclusion
  générale ni de gain mémoire établi.
- Étape I : comparaison externe avec `llama-cpp-python` sur six positions :
  premier token identique à chaque position, mais écart maximal de logits
  d'environ 1,669, dont la cause n'est pas établie. Un accord d'argmax ne
  démontre pas la justesse de tous les calculs.

L'exécution du prototype étudié est distincte de celle d'Ollama et de
`llama.cpp` ; des outils tiers ont servi à certaines comparaisons. Les essais
portent sur un modèle, des entrées courtes et une machine. Les performances,
la mémoire, le comportement long contexte et les autres plateformes restent à
évaluer. Aucune supériorité sur un autre moteur n'est revendiquée.
