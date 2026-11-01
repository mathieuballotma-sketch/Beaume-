# Démarrer avec Beaume

[Accueil](../README.md) · [Documentation](README.md)

Guide du prototype. La démonstration autonome est distincte de l’inférence réelle et de la reconstruction du corpus complet.
Employer un dossier public ou synthétique pour les premiers essais.

## 1. Installer le projet

Depuis le clone, avec Python 3.12 recommandé :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

`dev` installe pytest. L’extra `corpus` ajoute lxml pour les outils DILA :
`python -m pip install -e '.[dev,corpus]'`.
Les versions ne sont pas toutes verrouillées ; noter les versions réellement
installées pour reproduire une expérience.

## 2. Préparer Ollama

Installer et démarrer [Ollama](https://ollama.com/), puis télécharger le modèle
avant l’analyse. Dans le terminal qui exécutera Beaume :

```bash
ollama pull qwen2.5:7b-instruct
export OLLAMA_HOST=http://127.0.0.1:11434
export BEAUME_MODELE_OLLAMA=qwen2.5:7b-instruct
ollama list
```

Le modèle proposé est un point de départ expérimental, sans validation juridique.
Le défaut du code est `qwen-beaume-v1`, un nom de modèle créé localement : il n’est
pas installé par `pip` ni nécessairement disponible avec `ollama pull`.
Les poids Hugging Face publiés ne sont pas un paquet Ollama prêt à l’emploi.
La RAM, la latence et les résultats dépendent du modèle et du dossier.

## 3. Préparer le corpus — étape obligatoire

Le script d’analyse ouvre **`data/vector/legi_full.sqlite`**. Un clone neuf ne
contient pas cette base. Le script refuse de continuer si elle manque.

Le téléchargement historique peut la construire :

```bash
PYTHONPATH=. python scripts/telecharger_corpus.py
```

Il utilise `VinceGx33/legi-french-law-2025` sur Hugging Face et sélectionne cinq
codes par défaut. Il télécharge des données, consomme du disque et du temps.
**Ce corpus historique n’est pas une garantie de couverture des versions passées.**
Le nombre obtenu dépend de la ressource téléchargée. Le script ne remplace pas
une base déjà présente sans `--force` ; ne pas utiliser cette option sur une base
à conserver.

Pour le chantier des versions historiques DILA, lire [CORPUS_DILA.md](CORPUS_DILA.md).
Une base reconstruite séparément n’est pas automatiquement utilisée par l’analyse.
Ne pas substituer une base sans vérifier schéma, couverture et traçabilité.

### Essai technique sans corpus ni modèle

```sh
PYTHONPATH=. python scripts/demo_hors_ligne.py
```

Sortie : `data/out/demo_hors_ligne.md`. PDF, corpus et réponse fixes sont fictifs.
La commande refuse d’écraser un rapport existant ; choisir un autre `--sortie`.
Le mode historique `BEAUME_CORPUS_DEMO=1` de `analyser_dossier.py` reste distinct
et dépend d’un corpus local non distribué. Il n’est pas requis pour cet essai.

## 4. Analyser un exemple

Placer des PDF contenant du texte sélectionnable dans `data/inbox/exemple_public/`.
Le lecteur inspecte les fichiers immédiats, pas récursivement les sous-dossiers.
Le pipeline nominal ne fournit pas d’OCR des scans.

```bash
PYTHONPATH=. python scripts/analyser_dossier.py data/inbox/exemple_public 2024-01-01
```

Remplacer la date d’exemple par la date de référence choisie pour l’expérience.
Sans date, le script utilise celle du jour. Une date unique ne représente pas
nécessairement toutes les dates juridiquement pertinentes d’une affaire.
Le rapport est écrit dans `data/out/exemple_public_analyse.md`.
Relire avertissements, citations rejetées et pièces ignorées avant d’interpréter
le contenu. `COMPLET` n’est pas une validation juridique ni une preuve d’exhaustivité.

## 5. Diagnostiquer un échec

| Symptôme | Vérification |
| --- | --- |
| Corpus absent | Chemin `data/vector/legi_full.sqlite` et préparation ci-dessus |
| Modèle absent | `ollama list` et `BEAUME_MODELE_OLLAMA` dans le même terminal |
| Connexion Ollama impossible | Service démarré et hôte local configuré |
| PDF vide ou mal lu | Texte sélectionnable ; absence de prise en charge OCR nominale |
| Aucun article pertinent | Corpus, date, candidats retrouvés, puis sélection du modèle |
| JSON ou analyse partiels | Avertissements et limites de contexte ; ne pas forcer un succès |

Pour signaler un problème, voir [CONTRIBUTING.md](../CONTRIBUTING.md).
