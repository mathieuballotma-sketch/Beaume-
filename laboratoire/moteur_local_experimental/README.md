# Prototype local expérimental

Ce dossier rassemble un prototype séparé du parcours principal de Beaume. Il ne doit pas être utilisé avec des dossiers clients. Aucun modèle ni binaire n'est fourni. Le PDF et le corpus joints sont fictifs ; les articles de ce corpus ne sont pas du droit réel.

## Code présent

- `cortex_minimal.py` et `parcours_vertical_v1.py` : parcours expérimental sur PDF fictif, journal des étapes, états partiels et signaux à examiner.
- `ancrage.py`, `detecter_contradictions.py`, `detecter_dates.py` : règles de rapprochement et de signalement, sans validation sémantique ou juridique.
- `premier_moteur.py` et `generateur_llama_cpp.py` : appels à l'exécutable `llama-completion` de **llama.cpp** et contrôles de sortie. Ce n'est pas un moteur d'inférence développé de bout en bout par Beaume.
- `vision_ocr.swift`, `ocr_vision.py`, `ocr_backend.py` : OCR utilisant Apple Vision sur macOS. L'interface commune existe, mais le parcours expérimental appelle encore directement l'adaptateur Vision. Le backend Tesseract est un squelette indisponible, pas une implémentation fonctionnelle.
- `profil_materiel.py` : détection et profils expérimentaux. Une compatibilité ou une fluidité sur tous les Mac disposant de 16 Go n'est pas démontrée.

Le modèle par défaut dans le code est un chemin local lié à une expérience antérieure. Il faut fournir explicitement un fichier GGUF disponible sur sa propre machine ainsi qu'un exécutable compatible pour toute nouvelle exécution. Le nom d'un fichier et sa taille ne démontrent pas sa compatibilité ou sa qualité pour une tâche.

## Tests reproductibles

Les tests ciblés ci-dessous utilisent Python 3.12 et des données fabriquées ou des doublures : ils ne lancent pas une analyse réelle avec modèle.

```sh
cd laboratoire/moteur_local_experimental
python3.12 -m unittest -q test_ancrage_v3 test_contradictions_v2 test_dedup test_detecter_contradictions test_detecter_dates test_generateur_llama_cpp test_inspecteur_gguf test_premier_moteur test_validateur_beaume test_verrou_cache
```

**165 tests réussis** sur la copie publiée le 15 novembre 2026. Avec PyMuPDF et pytest installés, 35 tests supplémentaires des modules `test_cortex_minimal.py`, `test_parcours_vertical_v1.py` et `test_post_filtre_v2.py` ont réussi ; l'unique test de ces modules qui peut lancer un modèle réel a été exclu de cette exécution. La suite complète a aussi des tests dépendant du matériel macOS, d'une image ou de l'OCR. Dans la session isolée de publication, certains n'ont pas pu être reproduits : la détection mémoire ne renvoyait pas les informations nécessaires et Apple Vision ne traitait pas l'image disponible. Ce résultat ne démontre ni une panne du Mac ni la réussite de ces tests.

Sur macOS, le binaire OCR peut être compilé depuis ce répertoire avec les outils de développement Apple :

```sh
mkdir -p bin
swiftc vision_ocr.swift -o bin/vision_ocr
```

Il faut aussi PyMuPDF pour le parcours PDF. La compilation ou les tests précédents ne prouvent pas la qualité de l'OCR sur des scans papier dégradés, ni la compatibilité Windows ou Linux. Les coordonnées OCR ne constituent pas une navigation vérifiée.

## Confidentialité et portée

Le cache de prompt est désactivé par défaut dans le générateur ; des options expérimentales permettent néanmoins de l'activer. Un cache peut contenir les tokens du dossier et doit être considéré comme sensible. L'OCR utilise temporairement des images de pages sur disque. Les journaux et fichiers temporaires demandent un examen avant tout usage sensible : une exécution locale ne suffit pas à garantir la confidentialité.

Les affirmations, dates et signaux produits sont des propositions à vérifier. Le compteur de pages lues ne mesure pas la couverture des faits. Un texte retrouvé sur une page n'établit pas le sens de la phrase, l'absence d'erreur ou l'applicabilité d'un article.
