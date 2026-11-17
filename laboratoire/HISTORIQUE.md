# Briques expérimentales publiées

Ces expériences sont séparées du parcours principal et utilisent des données fictives. Elles ont été conçues pour examiner des fonctions précises ; leurs tests ne prouvent pas une qualité générale ou juridique.

| Brique | Fonction examinée | Limite principale |
| --- | --- | --- |
| [Signalement](signalement_v3/) | Repérage de motifs et émission de signaux à examiner | Un signal n'établit pas une contradiction, son absence ne prouve rien |
| [Attention de référence](calcul_reference/) | Calcul pédagogique d'attention à partir de vecteurs fournis | Aucun modèle complet n'est chargé |
| [Prototype local](moteur_local_experimental/) | Étapes d'un parcours fictif, génération avec `llama.cpp` et OCR Apple | Distinct du produit principal ; qualité et sécurité non validées |
| [Calcul matriciel](calcul_matrices_apple/) | Multiplication de matrices sur CPU et Metal | Opération isolée, pas un moteur de LLM ni un benchmark |
| [Inférence Swift expérimentale](inference_swift_experimentale/) | Sources de lecture GGUF, calculs quantifiés et forward | Recherche isolée ; fidélité et généralisation non établies |

Les commandes de test et les conditions connues sont décrites dans les dossiers correspondants. Un passage retrouvé et un passage qui étaye une affirmation sont deux vérifications distinctes.
