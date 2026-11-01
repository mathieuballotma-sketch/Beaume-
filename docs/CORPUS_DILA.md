# Corpus LEGI officiel pour Beaume

## Périmètre et statut

Ce chantier prépare les textes juridiques de référence **avant** l'entraînement
ou le changement du moteur de recherche. Il ne produit pas de labels de
pertinence et ne démontre pas la fiabilité juridique de Beaume.

La collecte est isolée dans `data/vector/legi_dila_v2/`. Elle ne modifie ni
`legi_full.sqlite`, ni les données clients, ni le pipeline de production.
Le contenu de `data/` est déjà ignoré par Git.

Sources officielles :

- Stock et flux : <https://echanges.dila.gouv.fr/OPENDATA/LEGI/>.
- DTD : <https://echanges.dila.gouv.fr/OPENDATA/DTD_LEGIFRANCE/>.
- Description du producteur : <https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides>.
- Licence Ouverte / Open Licence 2.0 : <https://www.data.gouv.fr/pages/legal/licences/etalab-2.0>.

Attribution : **DILA — Légifrance, base LEGI**. Le manifeste indique les URL,
le dernier lot, la date d'acquisition et les SHA-256 calculés localement.
Ces empreintes permettent de reproduire la photographie ; ce ne sont pas des
signatures fournies par la DILA.

## Reprendre la collecte

Depuis la racine du clone :

```sh
TMPDIR="$PWD/data/vector/legi_dila_v2/tmp" .venv/bin/python -m pip install --no-cache-dir -e '.[corpus]'
PYTHONPATH=. .venv/bin/python scripts/preparer_legi_dila.py --etape telecharger --workers 4
PYTHONPATH=. .venv/bin/python scripts/preparer_legi_dila.py --etape parser
```

Le répertoire `tmp` doit exister avant l'installation. L'étape de parsing
acquiert et extrait la DTD dans `data/vector/legi_dila_v2/dtd/`, puis fige
l'empreinte de l'archive et de chaque définition utilisée. L'archive est
`DTD_LEGIFRANCE_20181017.7z`. Pour une extraction manuelle sur ce Mac :

```sh
/usr/bin/tar -xf data/vector/legi_dila_v2/dtd/DTD_LEGIFRANCE_20181017.7z -C data/vector/legi_dila_v2/dtd
```

`manifest.json` fige le stock le plus récent de l'index enregistré et **tous**
les flux postérieurs, par horodatage complet. Il peut y avoir plusieurs flux
le même jour. Une nouvelle photographie doit utiliser un nouveau répertoire,
afin de ne pas changer silencieusement les sources d'un entraînement.

Les téléchargements sont repris et vérifiés ; chaque archive est appliquée
dans une transaction SQLite. Une archive déjà appliquée avec la même empreinte
est ignorée. Une empreinte différente provoque un arrêt explicite.

## Fichiers livrés

| Chemin sous `data/vector/legi_dila_v2/` | Rôle |
|---|---|
| `raw/` | Archives officielles compressées et index source |
| `dtd/` | DTD officielle et documentation associée |
| `manifest.json` | Sources ordonnées, tailles, dates et empreintes |
| `legi_dila.sqlite` | Corpus séparé de la production |
| `reports/couverture.json` | Mesures exploitables automatiquement |
| `reports/COUVERTURE.md` | Rapport lisible avant toute décision d'import |
| `reports/QUALITE_SOURCES.md` | Champs vides et anomalies DTD du corpus présent |
| `reports/qualite_sources.json` | Diagnostics de qualité structurés et chemins sources |
| `reports/CONFLITS_SOURCES.md` | Audit des copies divergentes et priorités de publication |
| `reports/conflits_sources.jsonl` | Toutes les copies à comparer, identifiants et empreintes |
| `quarantine/` | XML illisibles, conservés par empreinte |

La vue SQLite `versions_articles` fournit les sept champs demandés :

```sql
SELECT article_id, code, numero, date_debut, date_fin, statut, texte
FROM versions_articles;
```

Elle expose aussi le contexte, le contenu XML, les notes, les liens de versions,
la provenance exacte dans l'archive et les diagnostics DTD. Les archives brutes
permettent de retrouver le XML original complet.

Les titres des codes sont disponibles dans `codes_metadata`. Cette vue filtre
les documents `TEXTE_VERSION` : le fichier `TEXTELR` du même identifiant décrit
la structure et possède normalement un titre vide. Une jointure sur le seul
identifiant, sans distinguer ces racines, peut retourner un titre vide ou
multiplier les résultats.

```sql
SELECT code, titre, source_archive FROM codes_metadata;
```

## Choix de représentation

1. **LEGIARTI identifie une version.** Le numéro n'est jamais la clé.
   Les renumérotations restent visibles dans les métadonnées et liens officiels.
2. `code` est le CID **LEGITEXT du parent de nature CODE**. Un texte non
   codifié reste présent avec `code = NULL` et son identifiant dans `texte_id`.
   Un contexte parent incomplet peut aussi produire `code = NULL` : le rapport
   distingue l'absence de code identifié des textes non codifiés identifiés.
   Un article mentionnant un code n'appartient pas pour autant à ce code.
3. Les familles sont calculées uniquement via `VERSIONS/VERSION/LIEN_ART`.
   `article_famille_id` est un identifiant dérivé, pas un CID officiel.
   Les références externes JORF sont comptées séparément des références LEGI
   manquantes. Ces familles ne garantissent pas une continuité normative :
   un même numéro peut être réutilisé pour une autre règle ; une même règle
   peut changer de numéro et appartenir à une autre famille.
4. Les documents sources sont indexés **par chemin**. Une suppression DILA
   peut accompagner un déplacement vigueur/abrogé. Les suppressions sont
   appliquées avant les remplacements du flux, sans supprimer un ID partout.
5. Les dates et statuts restent bruts. Les valeurs vides, `2999-01-01`,
   `2222-02-22`, états différés et notes nécessitent un traitement explicite
   lors de la préparation des exemples. Ils ne deviennent pas des échéances
   certaines par le simple fait d'avoir le format d'une date.
6. Les paragraphes, sauts de ligne, contenus mixtes XHTML et notes sont
   conservés. Aucun `recover=True` ne répare silencieusement un XML invalide.
7. Le parsing strict et la conformité à la DTD publiée sont deux contrôles
   distincts. La DTD de 2018 peut ne pas décrire toutes les évolutions du flux :
   les diagnostics sont conservés pour examen, sans supprimer les textes.
8. Les fichiers ELI `versions.xml` sont des alias de résolution. Les racines
   `ID` et `VERSIONS` ne sont pas des versions d'articles supplémentaires.
   Certains alias officiels sont vides : ils sont conservés en quarantaine
   et comptés séparément des erreurs sur le contenu juridique. Leur contenu
   ne doit pas être inventé pour faire passer un contrôle.


## Ressources

Le stock complet et ses index occupent plusieurs dizaines de Go selon la photographie, les archives et les intermédiaires conservés. Le volume exact varie. Pour essayer le code sans ce téléchargement, utiliser la démonstration du guide de démarrage.
