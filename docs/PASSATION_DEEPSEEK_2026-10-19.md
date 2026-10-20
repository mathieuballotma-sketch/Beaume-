# Passation technique Beaume — 19 octobre 2026

Ce document est destiné à être transmis à DeepSeek pour reprendre le travail sur le dépôt. Il décrit les changements réalisés pendant l’audit, les mesures exécutées, les limites constatées et la méthode à suivre pour continuer proprement.

## Instructions de travail pour DeepSeek

Tu m’aides à faire progresser Beaume, un assistant juridique local destiné aux avocats. Tu n’as pas accès à mon dépôt ni à mon Mac. Ne prétends donc jamais avoir lu, modifié ou testé un fichier tant que je ne t’ai pas transmis son contenu ou les résultats de la commande correspondante. Donne-moi des commandes prêtes à exécuter depuis le dépôt, puis attends que je te renvoie les sorties nécessaires.

Travaille comme un ingénieur senior en recherche d’information, logiciels juridiques, évaluation de modèles et qualité logicielle :

- Commence par vérifier la version réelle des fichiers et `git status`. Les anciens extraits et comptes rendus peuvent être dépassés.
- Avant de proposer un changement, explique le chemin des données dans le code et formule le défaut comme une hypothèse vérifiable.
- Fais des modifications ciblées. Ne remplace pas un fichier complet quand un petit diff suffit. Préserve les changements locaux déjà présents.
- Pour chaque correctif, indique le fichier, le comportement avant/après, un test de régression et la commande exacte à lancer.
- Sépare toujours **implémenté**, **exécutable**, **testé** et **validé**. Un test vert ne prouve pas la pertinence juridique.
- Quand une fonctionnalité ou une dépendance a pu changer, vérifie sa documentation officielle actuelle et la version réellement installée. Pour les questions juridiques, privilégie les sources officielles. Cite les sources, leur date/version et ce qu’elles permettent réellement de conclure.
- Ne transmets jamais de documents clients, de noms de clients, de secrets ou de contenu confidentiel à un service externe. Pour les échanges avec toi, utilisons des données synthétiques ou des extraits de code expurgés.
- Ne commit/push rien sans demande explicite. Ne fais pas de `git reset --hard`, `git checkout --` ou écrasement des modifications locales.

Quand une information manque, ne devine pas. Demande la commande minimale qui permet de l’obtenir et continue le travail indépendant de cette information.

## Projet et objectif produit

Beaume vise à analyser un dossier juridique directement sur la machine de l’avocat, produire une synthèse structurée et relier les affirmations aux pièces du dossier (fichier et page) ainsi qu’aux versions pertinentes des textes officiels. Le résultat recherché est un outil qui fait gagner du temps tout en permettant à l’avocat de vérifier l’origine de chaque élément.

La valeur de Beaume ne repose pas sur le fait d’avoir entraîné un modèle. Elle repose sur le résultat vécu : retrouver les éléments utiles, montrer d’où ils viennent, citer le droit dans sa version applicable et signaler clairement ce qui n’a pas pu être vérifié. Le fonctionnement local peut aider à protéger les dossiers, mais il ne suffit pas à prouver la sécurité, la conformité ou la fiabilité juridique. Beaume reste un prototype de R&D ; il ne remplace pas le jugement de l’avocat.

L’utilisateur développe seul, avec des ressources limitées, et n’a pas encore d’avocat disponible pour annoter les données. Les jeux de test actuels doivent donc rester explicitement marqués comme synthétiques/provisoires, pas comme vérité juridique validée.

## Modifications réalisées pendant l’audit

### 1. Distinguer un numéro absent d’un article introuvable

**Fichiers concernés :**

- `beaume/legal/model.py`
- `beaume/adapters/verificateur_standard.py`
- `tests/unit/test_verificateur_citations.py`

Le modèle a généré deux citations avec `code_travail`, un extrait, mais un numéro d’article vide. Le vérificateur les classait `INTROUVABLE`. Ce statut signifie normalement que Beaume a cherché une référence qui n’existe pas dans son corpus ; il ne décrivait donc pas exactement l’erreur observée.

J’ai ajouté `StatutVerification.NUMERO_MANQUANT` et une vérification précoce dans `VerificateurStandard`. Une citation sans numéro reçoit désormais `numero_manquant`, avant toute recherche dans SQLite. Un test couvre ce cas.

### 2. Vérifier l’existence d’un article sans choisir deux dates arbitraires

**Fichiers concernés :**

- `beaume/ports/depot_articles.py`
- `beaume/adapters/depot_sqlite.py`
- `beaume/adapters/verificateur_standard.py`
- `tests/unit/test_verificateur_citations.py`

L’ancienne logique essayait de savoir si l’article existait à une autre date en interrogeant le dépôt au `1900-01-01` et au `2100-01-01`. Cela ne prouve pas qu’un article n’existe pas : une version peut être valable uniquement entre ces deux dates. Il était alors possible de confondre `VERSION_INCORRECTE` et `INTROUVABLE`.

J’ai ajouté au contrat `DepotArticles` la méthode `article_existe(code, numero)`. `DepotSQLite` cherche directement une ligne correspondante dans `articles` et `versions`, sans date. Le vérificateur peut alors dire : article connu, mais aucune version applicable à la date demandée. Un test de régression utilise une version bornée de 2000 à 2010 et la vérifie en 2020.

**À préserver :** `depot_sqlite.py` comportait déjà d’autres changements locaux, notamment le mode lecture seule utilisé par le benchmark. Ne remplace pas ce fichier par une version reconstruite à partir du seul ajout `article_existe`.

### 3. Rendre le benchmark capable d’expliquer les échecs

**Fichiers concernés :**

- `scripts/bench_qualite.py`
- `tests/unit/test_benchmarks.py`
- Résultat local : `data/logs/bench_qualite_diagnostic_2026-10-19.json`

Le simple rappel final ne disait pas si une référence attendue était absente des candidats, si le modèle ne l’avait pas choisie, ou si son extrait avait été rejeté. Le benchmark trace maintenant les résultats FTS5 de chaque chunk, reconstitue les candidats effectivement disponibles dans le prompt à la date du dossier, puis consigne pour chaque citation son code, son numéro, son statut de vérification, la présence de l’article parmi les candidats et la présence d’un extrait.

Le nombre `5` est une limite **par chunk**. Un dossier composé de plusieurs chunks peut donc transmettre plus de cinq articles au total. Le rapport enregistre le nombre d’appels et l’union exacte des candidats applicables transmis au modèle ; il ne suppose pas qu’un dossier entier ne reçoit que cinq articles.

Le benchmark ne plante plus quand une sortie du modèle contient un numéro vide ou invalide : elle est consignée comme échec diagnostique. Des tests couvrent le calcul de couverture, la différence entre candidats récupérés et candidats transmis, les statuts de citation et les numéros vides.

**Attention au périmètre local :** `scripts/bench_qualite.py` était déjà modifié et `tests/unit/test_benchmarks.py` déjà présent comme nouveau fichier dans l’arbre de travail au début de cette intervention. Mes ajouts portent sur la traçabilité des candidats/statuts et la tolérance aux références mal formées. Cette note ne m’attribue pas tous les changements du diff complet ; relis ces fichiers avant tout remplacement ou commit.

## Mesures exécutées

Environnement de cette vérification : dépôt `/Users/mathieubellot/Projets/beaume`, corpus `data/vector/legi_full.sqlite` (25 767 articles), modèle Ollama `qwen-beaume-v1`, date de référence `2025-01-01`.

La suite complète a été exécutée après les corrections : **310 tests passés, 2 ignorés**. `git diff --check` ne signale pas d’erreur d’espacement.

Le benchmark réel du dépôt a été exécuté sur les cinq dossiers synthétiques. Il a terminé sans erreur d’exécution, en environ 9,4 secondes par dossier en moyenne :

| Mesure | Résultat |
|---|---:|
| Références `must_cite` annotées | 6 |
| Références présentes parmi les candidats effectivement transmis | 4/6 (66,7 %) |
| Références valides produites par le pipeline | 1/6 (16,7 %) |
| Citations rejetées | 5 |
| Statuts des citations rejetées | 2 `numero_manquant`, 3 `texte_different` |

| Dossier | Références attendues dans les candidats | Résultat observé |
|---|---:|---|
| BE-LECO-001 | 1/1 | L1233-3 valide |
| BE-LECO-002 | 0/2 | Deux citations sans numéro |
| BE-LECO-003 | 1/1 | L1233-3 rejeté pour extrait différent ; L2312-59 valide mais hors `must_cite` |
| BE-LECO-004 | 1/1 | L1233-4 rejeté pour extrait différent |
| BE-LECO-005 | 1/1 | L1233-5 rejeté pour extrait différent |

Le JSON local contient le détail par dossier et les candidats transmis. Le répertoire `data/` est ignoré par Git dans ce dépôt ; le rapport est donc présent sur le Mac mais n’est pas inclus dans un commit.

Un contrôle lexical séparé a montré que, pour BE-LECO-002, L1233-2 existe bien dans le corpus mais se trouve au rang 370 avec la requête FTS5 large actuelle. Une requête manuelle plus ciblée sur « licenciement / motif / économique » le fait remonter au rang 3. L1233-1 existe également dans le corpus, mais ne ressort pas avec les mots extraits du dossier. C’est un indice de mauvaise sélection des termes et de limites morphologiques du FTS5, pas encore une preuve qu’un algorithme de remplacement sera meilleur en général.

## Interprétation correcte — ce qui est réparé et ce qui reste à faire

Les réparations effectuées concernent le **diagnostic** et la **classification d’erreurs**. Elles ne rendent pas le modèle ou le moteur de recherche plus fiables par elles-mêmes.

- Pour BE-LECO-002, le modèle n’a pas inventé un numéro : il n’en a fourni aucun. Le statut `numero_manquant` expose maintenant cette erreur.
- Pour les trois autres rejets, les articles `must_cite` étaient bien parmi les candidats transmis, mais les extraits fournis n’étaient pas une copie vérifiable du texte officiel. Le candidat était disponible ; le pipeline n’a pourtant pas produit une citation valide.
- Pour BE-LECO-002, les deux références attendues ne faisaient pas partie des candidats transmis. Le modèle ne pouvait pas sélectionner ces articles dans ce prompt. Toutefois, les annotations `must_cite` sont provisoires et non relues par un juriste : il faut aussi vérifier qu’elles sont pertinentes et que les deux sont réellement attendues.
- Le résultat `1/6` est un signal de défaut sur ce petit jeu, pas une estimation robuste de la qualité générale de Beaume.

Évite les affirmations telles que « le problème ne reviendra pas » après quelques cas réussis. Une amélioration observée sur trois dossiers prouve seulement que ces trois générations ont terminé dans ces conditions ; il faut des tests de non-régression et davantage de dossiers pour mesurer la fréquence des échecs.

## Méthode à appliquer pour les prochains problèmes

Quand plusieurs composants peuvent expliquer un mauvais résultat, sépare-les au lieu de choisir une cause au ressenti :

1. **Reproduire** avec une commande et un jeu fixe. Noter la version du code, le modèle, le corpus, la date de référence et les paramètres.
2. **Suivre le flux réel** : texte extrait → chunks → requête de recherche → résultats ordonnés → articles filtrés selon la date → prompt réellement envoyé → JSON du modèle → parsing → vérification contre le texte officiel → rapport.
3. **Mesurer chaque étape**. Pour un échec de citation, enregistrer le statut exact et si l’article attendu était réellement présent dans le prompt. « Le FTS5 a renvoyé cinq résultats » ne répond pas à cette question.
4. **Formuler une hypothèse étroite**. Exemple : « la requête OR avec tous les mots du chunk fait descendre L1233-2 au-delà du top 5 ».
5. **Changer une seule chose**, garder une baseline, puis comparer avec les mêmes dossiers, le même corpus, la même date et le même modèle.
6. **Ajouter un test de régression** sur la cause exacte, puis lancer la suite pertinente et la suite complète.
7. **Présenter les limites** : cinq cas synthétiques ne prouvent ni la performance sur des dossiers réels ni la fiabilité juridique.

Pour effectuer une recherche approfondie sur une fonctionnalité ou une dépendance :

- Commence par la version réellement installée (`ollama --version`, version du paquet, version SQLite, version du modèle), puis lis la documentation officielle correspondant à cette version.
- Vérifie ce que le code appelle vraiment : arguments envoyés, schéma, paramètres par défaut, exceptions, gestion du timeout et chemin de données. Le nom d’une fonction ou un commentaire ne prouvent pas son comportement.
- Cherche une source primaire (documentation officielle, code source maintenu, spécification) et, si possible, un test minimal reproductible. N’extrapole pas un comportement observé dans une version à toutes les versions.
- Distingue ce que la documentation affirme, ce que le code implémente et ce que l’expérience locale a mesuré.
- Pour la recherche juridique, vérifie les identifiants, la version applicable à la date et le texte officiel. Une référence citée dans un fait synthétique généré par un LLM n’est pas une annotation de vérité.
- Demande-moi des sorties ciblées si tu ne peux pas accéder au dépôt. Par exemple : `git status --short`, `git diff -- fichier`, une commande de test précise ou un JSON expurgé. Ne demande pas des PDF clients si des logs structurés suffisent.

## Prochaines étapes recommandées

1. **Améliorer la mesure du retrieval**, avant de modifier le FTS5 : mesurer Recall@5, @10 et le rang complet sur davantage de références, avec des références contrôlées. Vérifier les articles attendus dans le corpus et à la date retenue.
2. **Comparer des variantes de recherche** sur le même jeu : FTS5 actuel, requêtes ciblées, normalisation morphologique française et éventuellement fusion de classements. Ne règle pas les paramètres uniquement sur BE-LECO-002.
3. **Éviter de laisser le modèle recopier le texte de loi** : étudier un format de sortie où le modèle sélectionne un identifiant d’article parmi les candidats, puis où l’application récupère elle-même la version officielle et l’extrait depuis SQLite. Tester ce flux avant de le considérer comme correct.
4. **Séparer les métriques** : rappel de recherche, sélection du bon article, validité du texte officiel, qualité de l’analyse, traçabilité fichier/page et erreurs d’extraction PDF.
5. **Améliorer les annotations**. Tant qu’aucun juriste n’est disponible, conserver le statut provisoire, documenter la méthode et éviter de présenter les `must_cite` comme vérité terrain. Plus tard, solliciter une revue ciblée d’un échantillon via un réseau ouvert de juristes.

## Commandes utiles sur le Mac

Depuis le dépôt :

```bash
cd /Users/mathieubellot/Projets/beaume
git status --short
git diff --check
TMPDIR=/private/tmp PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/pytest -q
TMPDIR=/private/tmp PYTHONPATH=. .venv/bin/python scripts/bench_qualite.py \
  --modele qwen-beaume-v1 \
  --sortie data/logs/bench_qualite_diagnostic.json
```

Le benchmark appelle Ollama localement et doit avoir accès au service `127.0.0.1:11434`. Son entrée actuelle est synthétique. Avant toute exécution sur un autre jeu, vérifier qu’il ne contient pas de documents clients et que les annotations sont documentées.

## État Git à la passation

Les changements sont locaux et non commités. Le dépôt contenait déjà plusieurs modifications et nouveaux fichiers avant ou pendant cet audit, notamment autour des benchmarks, du dataset, du prompt et de l’entraînement. Préserve-les. Avant un commit, examine le diff fichier par fichier et sépare clairement les changements de cette intervention des autres changements locaux. Aucun commit ni push n’a été effectué.


## Code complet des fichiers à transmettre à DeepSeek

Les blocs ci-dessous sont des instantanés complets des fichiers actuels sur le Mac. Certains contiennent des changements locaux antérieurs à cet audit, notamment `depot_sqlite.py`, `bench_qualite.py` et `test_benchmarks.py`. Ils sont inclus pour donner à DeepSeek le contexte réel ; cela ne signifie pas que chaque ligne a été modifiée pendant cette intervention.

### `beaume/legal/model.py`

````python
"""Ontologie juridique Beaume.

Regle d'or : un article n'existe qu'a une date. Toute citation doit
porter une date de reference. Le verificateur est la seule autorite
qui decide si une citation est valide.
"""
from datetime import date
from enum import Enum

from pydantic import BaseModel

from beaume.legal.ids import IdentifiantLegifrance


class CodeJuridique(str, Enum):
    """Codes juridiques francais."""
    CODE_CIVIL = "code_civil"
    CODE_PENAL = "code_penal"
    CODE_TRAVAIL = "code_travail"
    CODE_COMMERCE = "code_commerce"
    CODE_CONSOMMATION = "code_consommation"
    CODE_SECURITE_SOCIALE = "code_securite_sociale"
    CODE_PROCEDURE_CIVILE = "code_procedure_civile"
    CODE_PROCEDURE_PENALE = "code_procedure_penale"
    CODE_SANTE_PUBLIQUE = "code_sante_publique"
    CODE_RURAL = "code_rural"
    CODE_TRANSPORTS = "code_transports"
    CODE_ENVIRONNEMENT = "code_environnement"
    CODE_COLLECTIVITES_TERRITORIALES = "code_collectivites_territoriales"
    CODE_MONETAIRE_FINANCIER = "code_monetaire_financier"
    CODE_EDUCATION = "code_education"
    CODE_CONSTRUCTION_HABITATION = "code_construction_habitation"
    CODE_ACTION_SOCIALE_FAMILLES = "code_action_sociale_familles"
    CODE_DEFENSE = "code_defense"
    CODE_FONCTION_PUBLIQUE = "code_fonction_publique"
    CODE_ENERGIE = "code_energie"
    CODE_SECURITE_INTERIEURE = "code_securite_interieure"
    CODE_ETRANGERS = "code_etrangers"
    CODE_URBANISME = "code_urbanisme"
    CODE_AUTRE = "code_autre"


class StatutVersion(str, Enum):
    EN_VIGUEUR = "en_vigueur"
    ABROGE = "abroge"
    MODIFIE = "modifie"
    FUTUR = "futur"
    INCONNU = "inconnu"


class VersionArticle(BaseModel, frozen=True):
    article_id: IdentifiantLegifrance
    numero: str
    date_debut: date
    date_fin: date | None = None
    texte: str
    statut: StatutVersion
    source: str

    def est_en_vigueur_a(self, d: date) -> bool:
        if d < self.date_debut:
            return False
        if self.date_fin is None:
            return True
        return d <= self.date_fin


class Article(BaseModel):
    id: IdentifiantLegifrance
    code: CodeJuridique
    numero: str
    versions: list[VersionArticle]

    def version_a(self, d: date) -> VersionArticle | None:
        for v in self.versions:
            if v.est_en_vigueur_a(d):
                return v
        return None


class Citation(BaseModel):
    code: CodeJuridique
    numero: str
    date_reference: date
    extrait: str | None = None
    # Nouveaux champs de tracabilite (2026-10-16).
    # - pages   : numeros de page du dossier ou le fait a ete trouve.
    # - fichier : nom du fichier source (ex: "conclusions.pdf").
    pages: tuple[int, ...] = ()
    fichier: str = ""


class StatutVerification(str, Enum):
    VALIDE = "valide"
    NUMERO_MANQUANT = "numero_manquant"
    INTROUVABLE = "introuvable"
    VERSION_INCORRECTE = "version_incorrecte"
    ABROGE = "abroge"
    TEXTE_DIFFERENT = "texte_different"
    EXTRAIT_MANQUANT = "extrait_manquant"


class ResultatVerification(BaseModel, frozen=True):
    statut: StatutVerification
    citation: Citation
    version: VersionArticle | None = None
    message: str = ""

    @property
    def est_valide(self) -> bool:
        return self.statut == StatutVerification.VALIDE
````

### `beaume/ports/depot_articles.py`

````python
"""Port : contrat d'un depot d'articles de loi.

Un depot sait :
- enregistrer des articles,
- retrouver la version en vigueur a une date,
- chercher par mots-cles (plein-texte),
- compter et vider.

Le port ne connait AUCUNE technologie de stockage concrete.
"""
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from beaume.legal.model import Article, CodeJuridique, VersionArticle


@dataclass(frozen=True)
class ResultatRechercheArticle:
    """Un resultat de recherche plein-texte dans le corpus."""
    article_id: str
    code: str
    numero: str
    extrait: str
    score: float


@runtime_checkable
class DepotArticles(Protocol):
    def enregistrer(self, articles: list[Article]) -> None: ...

    def trouver(
        self,
        code: CodeJuridique,
        numero: str,
        date_reference: date,
    ) -> tuple[Article, VersionArticle] | None: ...

    def article_existe(
        self,
        code: CodeJuridique,
        numero: str,
    ) -> bool: ...

    def trouver_par_id(
        self,
        article_id: str,
        date_reference: date,
    ) -> Article | None: ...

    def rechercher_texte(
        self,
        mots: str,
        limite: int = 10,
    ) -> list[ResultatRechercheArticle]: ...

    def compter(self) -> int: ...

    def vider(self) -> None: ...
````

### `beaume/adapters/depot_sqlite.py`

````python
"""Adaptateur SQLite : stockage persistant du corpus legal.

Utilise la stdlib sqlite3 + FTS5 pour la recherche plein-texte.
Aucune dependance externe. Aucune connexion reseau.

Le FTS5 est configurer avec 'remove_diacritics 2' pour ignorer les
accents a la recherche (delai = delai, ete = ete, etc.).
"""
import sqlite3
from datetime import date
from pathlib import Path

from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.normalisation import normaliser_numero
from beaume.legal.model import (
    Article,
    CodeJuridique,
    StatutVersion,
    VersionArticle,
)
from beaume.ports.depot_articles import ResultatRechercheArticle
from beaume.utils.logging import get_logger

log = get_logger("depot_sqlite")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    numero TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    article_id TEXT NOT NULL,
    numero TEXT NOT NULL,
    date_debut TEXT NOT NULL,
    date_fin TEXT,
    texte TEXT NOT NULL,
    statut TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (article_id, date_debut),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_versions_dates
    ON versions (article_id, date_debut, date_fin);

CREATE INDEX IF NOT EXISTS idx_articles_code_numero
    ON articles (code, numero);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    article_id UNINDEXED,
    code UNINDEXED,
    numero UNINDEXED,
    texte,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


class DepotSQLite:
    """Depot d'articles base sur SQLite + FTS5."""

    def __init__(self, chemin: Path, *, lecture_seule: bool = False) -> None:
        self.chemin = Path(chemin)
        if lecture_seule:
            if not self.chemin.is_file():
                raise FileNotFoundError(self.chemin)
            uri = f"{self.chemin.resolve().as_uri()}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.execute("PRAGMA query_only = ON")
        else:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.chemin))
        self._conn.row_factory = sqlite3.Row
        if not lecture_seule:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Ecriture
    # ------------------------------------------------------------------

    def enregistrer(self, articles: list[Article]) -> None:
        if not articles:
            return
        curseur = self._conn.cursor()
        for article in articles:
            curseur.execute(
                "INSERT OR REPLACE INTO articles (id, code, numero) "
                "VALUES (?, ?, ?)",
                (
                    article.id.valeur,
                    article.code.value,
                    normaliser_numero(article.numero),
                ),
            )
            # On purge les versions precedentes de cet article
            curseur.execute(
                "DELETE FROM versions WHERE article_id = ?",
                (article.id.valeur,),
            )
            for v in article.versions:
                curseur.execute(
                    "INSERT INTO versions ("
                    "  article_id, numero, date_debut, date_fin, "
                    "  texte, statut, source"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        v.article_id.valeur,
                        normaliser_numero(v.numero),
                        v.date_debut.isoformat(),
                        v.date_fin.isoformat() if v.date_fin else None,
                        v.texte,
                        v.statut.value,
                        v.source,
                    ),
                )
            # On purge la FTS pour cet article
            curseur.execute(
                "DELETE FROM articles_fts WHERE article_id = ?",
                (article.id.valeur,),
            )
            # On reindexe les versions
            for v in article.versions:
                curseur.execute(
                    "INSERT INTO articles_fts "
                    "(article_id, code, numero, texte) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        v.article_id.valeur,
                        article.code.value,
                        v.numero,
                        v.texte,
                    ),
                )
        self._conn.commit()
        log.info("Enregistre %d articles dans le depot", len(articles))

    def vider(self) -> None:
        curseur = self._conn.cursor()
        curseur.execute("DELETE FROM articles")
        curseur.execute("DELETE FROM versions")
        curseur.execute("DELETE FROM articles_fts")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def compter(self) -> int:
        (n,) = self._conn.execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()
        return int(n)

    def trouver(
        self,
        code: CodeJuridique,
        numero: str,
        date_reference: date,
    ) -> tuple[Article, VersionArticle] | None:
        iso = date_reference.isoformat()
        numero = normaliser_numero(numero)
        ligne = self._conn.execute(
            """
            SELECT a.id AS article_id, a.code AS code, a.numero AS numero,
                   v.date_debut, v.date_fin, v.texte, v.statut, v.source
            FROM articles a
            JOIN versions v ON v.article_id = a.id
            WHERE a.code = ?
              AND v.numero = ?
              AND v.date_debut <= ?
              AND (v.date_fin IS NULL OR v.date_fin >= ?)
            ORDER BY v.date_debut DESC
            LIMIT 1
            """,
            (code.value, numero, iso, iso),
        ).fetchone()

        if ligne is None:
            return None

        # Charge toutes les versions de cet article pour reconstruire l'Article.
        versions_rows = self._conn.execute(
            "SELECT numero, date_debut, date_fin, texte, statut, source "
            "FROM versions WHERE article_id = ? ORDER BY date_debut",
            (ligne["article_id"],),
        ).fetchall()

        versions = [
            VersionArticle(
                article_id=IdentifiantLegifrance(valeur=ligne["article_id"]),
                numero=r["numero"],
                date_debut=date.fromisoformat(r["date_debut"]),
                date_fin=(
                    date.fromisoformat(r["date_fin"]) if r["date_fin"] else None
                ),
                texte=r["texte"],
                statut=StatutVersion(r["statut"]),
                source=r["source"],
            )
            for r in versions_rows
        ]

        article = Article(
            id=IdentifiantLegifrance(valeur=ligne["article_id"]),
            code=CodeJuridique(ligne["code"]),
            numero=ligne["numero"],
            versions=versions,
        )

        version_trouvee = next(
            v for v in versions
            if v.date_debut <= date_reference
            and (v.date_fin is None or v.date_fin >= date_reference)
        )

        return article, version_trouvee

    def article_existe(
        self,
        code: CodeJuridique,
        numero: str,
    ) -> bool:
        """Indique si le corpus connaît une version quelconque de l'article.

        Cette recherche ignore volontairement la date : elle sert à distinguer
        un article absent du corpus d'un article connu mais sans version
        applicable à la date demandée.
        """
        ligne = self._conn.execute(
            """
            SELECT 1
            FROM articles a
            JOIN versions v ON v.article_id = a.id
            WHERE a.code = ? AND v.numero = ?
            LIMIT 1
            """,
            (code.value, normaliser_numero(numero)),
        ).fetchone()
        return ligne is not None

    def trouver_par_id(
        self,
        article_id: str,
        date_reference: date,
    ) -> Article | None:
        """Retrouve un Article complet par son identifiant."""
        ligne = self._conn.execute(
            "SELECT id, code, numero FROM articles WHERE id = ?",
            (article_id,),
        ).fetchone()
        if ligne is None:
            return None

        versions_rows = self._conn.execute(
            "SELECT numero, date_debut, date_fin, texte, statut, source "
            "FROM versions WHERE article_id = ? ORDER BY date_debut",
            (article_id,),
        ).fetchall()

        versions = [
            VersionArticle(
                article_id=IdentifiantLegifrance(valeur=article_id),
                numero=r["numero"],
                date_debut=date.fromisoformat(r["date_debut"]),
                date_fin=(
                    date.fromisoformat(r["date_fin"]) if r["date_fin"] else None
                ),
                texte=r["texte"],
                statut=StatutVersion(r["statut"]),
                source=r["source"],
            )
            for r in versions_rows
        ]

        return Article(
            id=IdentifiantLegifrance(valeur=ligne["id"]),
            code=CodeJuridique(ligne["code"]),
            numero=ligne["numero"],
            versions=versions,
        )

    def rechercher_texte(
        self,
        mots: str,
        limite: int = 10,
    ) -> list[ResultatRechercheArticle]:
        mots = (mots or "").strip()
        if not mots:
            return []
        if limite <= 0:
            raise ValueError("limite doit etre > 0")

        lignes = self._conn.execute(
            """
            SELECT article_id,
                   code,
                   numero,
                   bm25(articles_fts) AS score,
                   snippet(articles_fts, 3, '[', ']', '...', 20) AS extrait
            FROM articles_fts
            WHERE articles_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (mots, limite),
        ).fetchall()

        return [
            ResultatRechercheArticle(
                article_id=r["article_id"],
                code=r["code"],
                numero=r["numero"],
                extrait=r["extrait"],
                # bm25 retourne un score plus petit = plus pertinent.
                # On inverse le signe pour que grand = meilleur.
                score=-float(r["score"]),
            )
            for r in lignes
        ]
````

### `beaume/adapters/verificateur_standard.py`

````python
"""Adaptateur standard du verificateur de citations.

Confronte une Citation produite par le LLM au corpus legal.
Regles strictes :
  - Numero absent           -> NUMERO_MANQUANT
  - Article absent          -> INTROUVABLE
  - Aucune version a la date -> VERSION_INCORRECTE
  - Article abroge          -> ABROGE
  - Extrait non present     -> TEXTE_DIFFERENT
  - Sinon                   -> VALIDE

La comparaison d'extrait est insensible aux accents, a la casse et
aux espaces multiples, mais elle est STRICTE sur le contenu.
"""
import re
import unicodedata

from beaume.legal.model import (
    Citation,
    ResultatVerification,
    StatutVerification,
    StatutVersion,
)
from beaume.ports.depot_articles import DepotArticles
from beaume.utils.logging import get_logger

log = get_logger("verificateur")


def _normaliser(texte: str) -> str:
    """Normalise un texte pour comparaison : minuscules, sans accents,
    ponctuation -> espaces, espaces multiples -> 1 espace."""
    if not texte:
        return ""
    t = texte.lower()
    t = "".join(
        c for c in unicodedata.normalize("NFD", t)
        if unicodedata.category(c) != "Mn"
    )
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class VerificateurStandard:
    """Verificateur de citations base sur le DepotArticles."""

    def __init__(self, depot: DepotArticles) -> None:
        self.depot = depot

    def verifier(self, citation: Citation) -> ResultatVerification:
        if not citation.numero.strip():
            return ResultatVerification(
                statut=StatutVerification.NUMERO_MANQUANT,
                citation=citation,
                message="Numero d'article absent : reference incomplete.",
            )

        res = self.depot.trouver(
            citation.code, citation.numero, citation.date_reference,
        )

        if res is None:
            # Chercher l'existence independamment de la date evite de
            # manquer les articles dont toutes les versions sont bornees.
            if self.depot.article_existe(citation.code, citation.numero):
                return ResultatVerification(
                    statut=StatutVerification.VERSION_INCORRECTE,
                    citation=citation,
                    message="Article connu mais aucune version a cette date.",
                )
            return ResultatVerification(
                statut=StatutVerification.INTROUVABLE,
                citation=citation,
                message="Article introuvable dans le corpus.",
            )

        article, version = res

        if version.statut == StatutVersion.ABROGE:
            return ResultatVerification(
                statut=StatutVerification.ABROGE,
                citation=citation,
                version=version,
                message="Article abroge a cette date.",
            )

        if not citation.extrait or not citation.extrait.strip():
            return ResultatVerification(
                statut=StatutVerification.EXTRAIT_MANQUANT,
                citation=citation,
                version=version,
                message="Aucun extrait fourni : citation non verifiable.",
            )

        if citation.extrait:
            extrait_norm = _normaliser(citation.extrait)
            texte_norm = _normaliser(version.texte)
            if extrait_norm and extrait_norm not in texte_norm:
                return ResultatVerification(
                    statut=StatutVerification.TEXTE_DIFFERENT,
                    citation=citation,
                    version=version,
                    message="L'extrait cite ne figure pas dans le texte officiel.",
                )

        return ResultatVerification(
            statut=StatutVerification.VALIDE,
            citation=citation,
            version=version,
            message="",
        )

    def verifier_toutes(
        self, citations: list[Citation]
    ) -> list[ResultatVerification]:
        return [self.verifier(c) for c in citations]
````

### `scripts/bench_qualite.py`

````python
"""Benchmark de bout en bout sur des dossiers factuels synthetiques.

Les references `must_cite` sont positives et non exhaustives. Le rapport
mesure le rappel des references requises, sans assimiler les autres
citations a des faux positifs. Une execution de ce script est un test
operationnel sur le jeu indique, pas une validation juridique generale.

Le modele Ollama est parametrable via --modele (defaut : qwen-beaume-v1).
Le nom du modele est trace dans le rapport JSON pour eviter de comparer
deux executions produites par des modeles differents sans le savoir.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.generateur_ollama import GenerateurOllama
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.bench.metriques import (
    ReferenceArticle,
    charger_references_dossier,
    cle_article,
)
from beaume.config import paths
from beaume.ports.registre import RegistreExtracteurs


FICHIER_DEFAUT = Path(__file__).resolve().parents[1] / "beaume" / "bench" / "dossiers_test.json"
MODELE_DEFAUT = "qwen-beaume-v1"


class _ChercheurTrace:
    """Decorateur de benchmark qui garde les hits de chaque chunk."""

    def __init__(self, chercheur: ChercheurArticlesFTS5) -> None:
        self.chercheur = chercheur
        self.appels: list[list[Any]] = []

    def reinitialiser(self) -> None:
        self.appels.clear()

    def chercher(self, texte: str, limite: int = 5) -> list[Any]:
        resultats = self.chercheur.chercher(texte, limite=limite)
        self.appels.append(resultats)
        return resultats


def _charger_jeu(chemin: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with chemin.open(encoding="utf-8") as fichier:
        data = json.load(fichier)
    if not isinstance(data, dict) or not isinstance(data.get("dossiers"), list):
        raise ValueError("Le fichier doit contenir une liste 'dossiers'.")
    meta = data.get("_meta", {})
    if not isinstance(meta, dict):
        raise ValueError("La metadonnee '_meta' doit etre un objet.")
    dossiers = data["dossiers"]
    if not dossiers:
        raise ValueError("Le jeu ne contient aucun dossier.")
    for i, dossier in enumerate(dossiers, start=1):
        if not isinstance(dossier, dict) or not dossier.get("texte"):
            raise ValueError(f"Dossier {i} invalide : texte manquant.")
        dossier.setdefault("id", f"dossier-{i:03d}")
        charger_references_dossier(dossier, meta.get("code"))
    return meta, dossiers


def _creer_pdf(texte: str, chemin: Path) -> None:
    """Ecrit un dossier de test dans un PDF et refuse le texte tronque."""
    document = pymupdf.open()
    try:
        page = document.new_page()
        rect = pymupdf.Rect(50, 50, 545, 780)
        hauteur_restante = page.insert_textbox(rect, texte, fontsize=11)
        if hauteur_restante < 0:
            raise ValueError("Le texte de test depasse la page PDF temporaire.")
        document.save(str(chemin))
    finally:
        document.close()

    with pymupdf.open(str(chemin)) as verif:
        texte_extrait = "\n".join(page.get_text() for page in verif)
    mots_attendus = {mot.casefold() for mot in texte.split() if len(mot) >= 5}
    mots_extraits = {mot.casefold() for mot in texte_extrait.split()}
    manquants = mots_attendus - mots_extraits
    if manquants:
        raise ValueError(
            "Le PDF temporaire ne contient pas tous les mots du dossier de test."
        )


def _construire_pipeline(depot: DepotSQLite, modele: str) -> PipelineAnalyse:
    registre = RegistreExtracteurs()
    registre.enregistrer(ExtracteurPDF())
    chercheur = _ChercheurTrace(ChercheurArticlesFTS5(depot))
    return PipelineAnalyse(
        registre=registre,
        chercheur=chercheur,
        generateur=GenerateurOllama(modele=modele),
        depot=depot,
        verificateur=VerificateurStandard(depot),
    )


def _cle_verification(verification: Any) -> ReferenceArticle | None:
    citation = verification.citation
    code = getattr(citation.code, "value", citation.code)
    numero = citation.numero
    if not str(code or "").strip() or not str(numero or "").strip():
        return None
    try:
        return cle_article(str(code), str(numero))
    except (TypeError, ValueError):
        # Une sortie LLM invalide doit être consignée comme rejetée, pas faire
        # échouer le benchmark qui est justement chargé de la diagnostiquer.
        return None


def _diagnostic_couverture(
    references: set[ReferenceArticle],
    candidats: set[ReferenceArticle],
) -> dict[str, Any]:
    trouvees = references & candidats
    absentes = references - candidats
    return {
        "references_must_cite_dans_candidats": [list(x) for x in sorted(trouvees)],
        "references_must_cite_absentes_des_candidats": [list(x) for x in sorted(absentes)],
        "rappel_retrieval_must_cite": len(trouvees) / len(references) if references else 0.0,
    }


def _diagnostic_recherche(
    pipeline: PipelineAnalyse,
    date_reference: date,
    references: set[ReferenceArticle],
) -> dict[str, Any]:
    chercheur = pipeline.analyseur.chercheur
    if not isinstance(chercheur, _ChercheurTrace):
        return {
            "n_appels_recherche": 0,
            "limite_par_chunk": pipeline.analyseur.limite_articles,
            "candidats_fts5_par_chunk": [],
            "candidats_transmis_au_llm": [],
            **_diagnostic_couverture(references, set()),
        }

    candidats_par_chunk = []
    ids_uniques: set[str] = set()
    candidats_transmis: set[ReferenceArticle] = set()
    for index, resultats in enumerate(chercheur.appels, start=1):
        candidats_fts5 = []
        for resultat in resultats:
            cle = cle_article(resultat.code, resultat.numero)
            candidats_fts5.append({
                "article_id": resultat.article_id,
                "code": cle[0],
                "numero": cle[1],
            })
            if resultat.article_id in ids_uniques:
                continue
            ids_uniques.add(resultat.article_id)
            article = pipeline.depot.trouver_par_id(
                resultat.article_id, date_reference,
            )
            # Le prompt n'affiche un article que si une version est
            # applicable à sa date de référence.
            if article is None or article.version_a(date_reference) is None:
                continue
            candidats_transmis.add(
                cle_article(article.code.value, article.numero)
            )
        candidats_par_chunk.append({
            "chunk": index,
            "candidats_fts5": candidats_fts5,
        })

    return {
        "n_appels_recherche": len(chercheur.appels),
        "limite_par_chunk": pipeline.analyseur.limite_articles,
        "candidats_fts5_par_chunk": candidats_par_chunk,
        "candidats_transmis_au_llm": [
            list(x) for x in sorted(candidats_transmis)
        ],
        **_diagnostic_couverture(references, candidats_transmis),
    }


def _diagnostic_citations(
    rapport: Any,
    candidats_transmis: set[ReferenceArticle],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    details = []
    compteurs: Counter[str] = Counter()
    for verification in rapport.verifications:
        citation = verification.citation
        cle = _cle_verification(verification)
        statut = verification.statut.value
        compteurs[statut] += 1
        details.append({
            "code": citation.code.value,
            "numero": citation.numero,
            "statut_verification": statut,
            "est_valide": verification.est_valide,
            "article_dans_candidats": (
                cle in candidats_transmis if cle is not None else False
            ),
            "extrait_fourni": bool((citation.extrait or "").strip()),
        })
    return details, dict(sorted(compteurs.items()))


def _evaluer_dossier(
    dossier: dict[str, Any],
    meta: dict[str, Any],
    pipeline: PipelineAnalyse,
    date_reference: date,
    workdir: Path,
) -> dict[str, Any]:
    gold = charger_references_dossier(dossier, meta.get("code"))
    chercheur = pipeline.analyseur.chercheur
    if isinstance(chercheur, _ChercheurTrace):
        chercheur.reinitialiser()
    dossier_dir = workdir / str(dossier["id"])
    dossier_dir.mkdir(parents=True, exist_ok=True)
    _creer_pdf(dossier["texte"], dossier_dir / "dossier.pdf")

    debut = time.perf_counter()
    try:
        rapport, _ = pipeline.executer(dossier_dir, date_reference)
    except Exception as exc:
        diagnostic_recherche = _diagnostic_recherche(
            pipeline, date_reference, gold,
        )
        return {
            "id": dossier["id"],
            "statut_execution": "erreur",
            "type_erreur": type(exc).__name__,
            "duree_s": time.perf_counter() - debut,
            "references": [list(x) for x in sorted(gold)],
            "references_valides_trouvees": [],
            "references_manquantes": [list(x) for x in sorted(gold)],
            "nb_citations_rejetees": 0,
            "citations_detail": [],
            "statuts_citations": {},
            **diagnostic_recherche,
        }

    duree = time.perf_counter() - debut
    diagnostic_recherche = _diagnostic_recherche(
        pipeline, date_reference, gold,
    )
    candidats_transmis = {
        tuple(reference)
        for reference in diagnostic_recherche["candidats_transmis_au_llm"]
    }
    citations_detail, statuts_citations = _diagnostic_citations(
        rapport, candidats_transmis,
    )
    predictions = {
        cle
        for verification in rapport.verifications
        if verification.est_valide
        if (cle := _cle_verification(verification)) is not None
    }
    trouve = gold & predictions
    return {
        "id": dossier["id"],
        "statut_execution": "ok",
        "duree_s": duree,
        "references": [list(x) for x in sorted(gold)],
        "references_valides_trouvees": [list(x) for x in sorted(trouve)],
        "references_manquantes": [list(x) for x in sorted(gold - predictions)],
        "nb_citations_generees": len(rapport.verifications),
        "nb_citations_valides": len(rapport.citations_valides),
        "nb_citations_rejetees": len(rapport.citations_rejetees),
        "nb_citations_valides_hors_must_cite": len(predictions - gold),
        "rappel_must_cite": len(trouve) / len(gold),
        "citations_detail": citations_detail,
        "statuts_citations": statuts_citations,
        "modele": rapport.modele_llm,
        **diagnostic_recherche,
    }


def _calculer_agregats(resultats: list[dict[str, Any]]) -> dict[str, Any]:
    total_gold = sum(len(r["references"]) for r in resultats)
    total_hits = sum(len(r["references_valides_trouvees"]) for r in resultats)
    total_retrieval_hits = sum(
        len(r.get("references_must_cite_dans_candidats", []))
        for r in resultats
    )
    total_cases = len(resultats)
    erreurs = sum(r["statut_execution"] == "erreur" for r in resultats)
    statuts_citations: Counter[str] = Counter()
    for resultat in resultats:
        statuts_citations.update(resultat.get("statuts_citations", {}))
    succes_partiel = sum(bool(r["references_valides_trouvees"]) for r in resultats)
    succes_complet = sum(
        set(map(tuple, r["references_valides_trouvees"])) == set(map(tuple, r["references"]))
        for r in resultats
    )
    return {
        "n_dossiers": total_cases,
        "n_erreurs_execution": erreurs,
        "n_references_must_cite": total_gold,
        "rappel_micro_must_cite": total_hits / total_gold if total_gold else 0.0,
        "n_references_must_cite_dans_candidats": total_retrieval_hits,
        "rappel_micro_retrieval_must_cite": (
            total_retrieval_hits / total_gold if total_gold else 0.0
        ),
        "rappel_macro_must_cite": (
            sum(r["rappel_must_cite"] for r in resultats if "rappel_must_cite" in r)
            / total_cases
        ),
        "taux_dossiers_avec_au_moins_une_reference": succes_partiel / total_cases,
        "taux_dossiers_avec_toutes_les_references": succes_complet / total_cases,
        "n_citations_rejetees": sum(r.get("nb_citations_rejetees", 0) for r in resultats),
        "statuts_citations": dict(sorted(statuts_citations.items())),
        "n_citations_valides_hors_must_cite": sum(
            r.get("nb_citations_valides_hors_must_cite", 0) for r in resultats
        ),
        "duree_moyenne_s": (
            sum(r.get("duree_s", 0.0) for r in resultats if r["statut_execution"] == "ok")
            / max(1, sum(r["statut_execution"] == "ok" for r in resultats))
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fichier", type=Path, default=FICHIER_DEFAUT)
    parser.add_argument("--base", type=Path, default=paths.VECTOR / "legi_full.sqlite")
    parser.add_argument("--date-reference", type=date.fromisoformat, default=None)
    parser.add_argument("--sortie", type=Path, default=None)
    parser.add_argument(
        "--modele",
        default=MODELE_DEFAUT,
        help="Modele Ollama a tester (defaut : qwen-beaume-v1).",
    )
    args = parser.parse_args()
    if not args.fichier.is_file():
        parser.error(f"Jeu de test introuvable : {args.fichier}")
    if not args.base.is_file():
        parser.error(f"Corpus introuvable : {args.base}")

    meta, dossiers = _charger_jeu(args.fichier)
    date_brute = args.date_reference or meta.get("date_reference")
    if isinstance(date_brute, str):
        date_reference = date.fromisoformat(date_brute)
    elif isinstance(date_brute, date):
        date_reference = date_brute
    else:
        parser.error(
            "Date non definie : fournir --date-reference ou _meta.date_reference."
        )

    depot = DepotSQLite(args.base, lecture_seule=True)
    pipeline = _construire_pipeline(depot, args.modele)
    print(f"Dossiers : {len(dossiers)} | references : {meta.get('statut_annotations', 'non documente')}")
    print(f"Corpus   : {depot.compter()} articles | date : {date_reference.isoformat()}")
    print(f"Modele   : {args.modele}")

    resultats: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="beaume-bench-") as tmp:
        workdir = Path(tmp)
        for i, dossier in enumerate(dossiers, start=1):
            print(f"[{i}/{len(dossiers)}] {dossier['id']}...", end=" ", flush=True)
            resultat = _evaluer_dossier(dossier, meta, pipeline, date_reference, workdir)
            resultats.append(resultat)
            if resultat["statut_execution"] == "erreur":
                print(f"ERREUR ({resultat['type_erreur']})")
            else:
                print(
                    f"rappel must_cite={resultat['rappel_must_cite']:.0%}, "
                    f"retrieval={resultat['rappel_retrieval_must_cite']:.0%}, "
                    f"rejetees={resultat['nb_citations_rejetees']}"
                )

    resultat_final = {
        "type_evaluation": "pipeline_complet_synthetique",
        "jeu": str(args.fichier),
        "statut_annotations": meta.get("statut_annotations", "non_documente"),
        "date_reference": date_reference.isoformat(),
        "corpus": str(args.base),
        "n_articles_corpus": depot.compter(),
        "modele": args.modele,
        "metriques": _calculer_agregats(resultats),
        "resultats": resultats,
        "interpretation": (
            "Les must_cite sont des references positives non exhaustives et non relues par un juriste. "
            "Ces chiffres sont un diagnostic sur ce petit jeu synthetique, pas une validation juridique."
        ),
    }
    sortie = args.sortie or paths.TMP / f"bench_qualite_{args.modele.replace(':', '_')}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(resultat_final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultat_final["metriques"], ensure_ascii=False, indent=2))
    print(f"Rapport : {sortie}")
    return 1 if resultat_final["metriques"]["n_erreurs_execution"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
````

### `tests/unit/test_verificateur_citations.py`

````python
"""Tests du verificateur de citations."""
from datetime import date
from pathlib import Path

import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import (
    Article,
    Citation,
    CodeJuridique,
    StatutVersion,
    StatutVerification,
    VersionArticle,
)
from beaume.ports.verificateur_citations import VerificateurCitations


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"

EXTRAIT_1240 = "qui cause a autrui un dommage"
EXTRAIT_L1234_1 = "peut toujours cesser par la volonte d'une des parties contractantes"


def _verificateur(tmp_path) -> VerificateurStandard:
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    depot.enregistrer(SourceFichierLocal(FIXTURE).charger())
    return VerificateurStandard(depot)


def _citation(code, numero, d, extrait=None) -> Citation:
    return Citation(
        code=code,
        numero=numero,
        date_reference=d,
        extrait=extrait,
    )


def test_verificateur_respecte_contrat(tmp_path):
    v = _verificateur(tmp_path)
    assert isinstance(v, VerificateurCitations)


def test_article_existe_version_valide(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait=EXTRAIT_1240,
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE
    assert res.est_valide is True
    assert res.version is not None


def test_article_sans_extrait_est_rejete(tmp_path):
    """Une citation sans extrait n'est pas verifiable : EXTRAIT_MANQUANT."""
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.EXTRAIT_MANQUANT
    assert res.est_valide is False


def test_article_avec_extrait_vide_est_rejete(tmp_path):
    """Un extrait vide (espaces) compte comme absent."""
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="   ",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.EXTRAIT_MANQUANT


def test_article_existe_avec_extrait_correct(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="qui cause a autrui un dommage",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE


def test_article_existe_avec_extrait_different(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="phrase completement inventee qui n'est pas dans la loi",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.TEXTE_DIFFERENT
    assert res.est_valide is False


def test_article_inexistant(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.INTROUVABLE


def test_numero_article_absent_est_distingue_dun_article_introuvable(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_TRAVAIL, "", date(2025, 1, 1))

    res = v.verifier(c)

    assert res.statut == StatutVerification.NUMERO_MANQUANT
    assert res.est_valide is False


def test_article_avant_toutes_versions(tmp_path):
    v = _verificateur(tmp_path)
    c = _citation(CodeJuridique.CODE_CIVIL, "1240", date(1900, 1, 1))
    res = v.verifier(c)
    assert res.statut == StatutVerification.VERSION_INCORRECTE


def test_article_a_versions_bornees_est_connu_hors_de_sa_periode(tmp_path):
    """Une version uniquement entre 2000 et 2010 ne doit pas devenir
    INTROUVABLE lorsqu'on vérifie une date en 2020."""
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    identifiant = IdentifiantLegifrance(valeur="LEGIARTI000099999999")
    depot.enregistrer([
        Article(
            id=identifiant,
            code=CodeJuridique.CODE_TRAVAIL,
            numero="L. 9999-9",
            versions=[
                VersionArticle(
                    article_id=identifiant,
                    numero="L. 9999-9",
                    date_debut=date(2000, 1, 1),
                    date_fin=date(2010, 12, 31),
                    texte="Version historique de test.",
                    statut=StatutVersion.ABROGE,
                    source="fixture-test",
                )
            ],
        )
    ])
    verificateur = VerificateurStandard(depot)

    resultat = verificateur.verifier(
        _citation(
            CodeJuridique.CODE_TRAVAIL,
            "L. 9999-9",
            date(2020, 1, 1),
            extrait="extrait quelconque",
        )
    )

    assert resultat.statut == StatutVerification.VERSION_INCORRECTE


def test_article_apres_toutes_versions_sans_fin(tmp_path):
    """L'article 1240 est en vigueur sans date de fin."""
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2099, 1, 1),
        extrait=EXTRAIT_1240,
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE


def test_verifier_toutes_retourne_une_liste(tmp_path):
    v = _verificateur(tmp_path)
    citations = [
        _citation(
            CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
            extrait=EXTRAIT_1240,
        ),
        _citation(
            CodeJuridique.CODE_TRAVAIL, "L. 1234-1", date(2020, 1, 1),
            extrait=EXTRAIT_L1234_1,
        ),
        _citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1)),
    ]
    resultats = v.verifier_toutes(citations)
    assert len(resultats) == 3
    assert resultats[0].statut == StatutVerification.VALIDE
    assert resultats[1].statut == StatutVerification.VALIDE
    assert resultats[2].statut == StatutVerification.INTROUVABLE


def test_melange_verdicts(tmp_path):
    """On passe un melange de citations et on verifie chaque verdict."""
    v = _verificateur(tmp_path)

    cas = [
        (_citation(
            CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
            extrait=EXTRAIT_1240,
        ), StatutVerification.VALIDE),
        (_citation(CodeJuridique.CODE_CIVIL, "9999", date(2020, 1, 1)),
         StatutVerification.INTROUVABLE),
        (_citation(CodeJuridique.CODE_CIVIL, "1240", date(1900, 1, 1)),
         StatutVerification.VERSION_INCORRECTE),
        (_citation(
            CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
            extrait="invente totalement",
        ), StatutVerification.TEXTE_DIFFERENT),
        (_citation(CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1)),
         StatutVerification.EXTRAIT_MANQUANT),
    ]

    for citation, attendu in cas:
        res = v.verifier(citation)
        assert res.statut == attendu, f"Attendu {attendu}, obtenu {res.statut}"


def test_extrait_normalise_accents(tmp_path):
    """Un extrait avec accents differents doit quand meme matcher."""
    v = _verificateur(tmp_path)
    c = _citation(
        CodeJuridique.CODE_CIVIL, "1240", date(2020, 1, 1),
        extrait="TOUT FAIT QUELCONQUE DE L'HOMME",
    )
    res = v.verifier(c)
    assert res.statut == StatutVerification.VALIDE
````

### `tests/unit/test_benchmarks.py`

````python
"""Tests des metriques de retrieval et de l'audit structurel des jeux."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.bench.metriques import calculer_rappel, charger_references_dossier
from beaume.legal.model import Citation, CodeJuridique, StatutVerification
from beaume.ports.depot_articles import ResultatRechercheArticle
from scripts.bench_qualite import (
    _ChercheurTrace,
    _calculer_agregats,
    _diagnostic_citations,
    _diagnostic_couverture,
    _diagnostic_recherche,
)
from scripts.generer_dataset_ft import _construire_conversation
from scripts.verifier_dataset import verifier_ligne


def test_metriques_rappel_micro_macro_mrr_et_hit_rate():
    a = ("code_travail", "L1233-3")
    b = ("code_travail", "L1233-4")
    c = ("code_travail", "L1233-5")
    d = ("code_travail", "L1233-6")

    resultat = calculer_rappel(
        references=[{a, b}, {c}],
        classements=[[a, d], [d, c]],
        k_values=(1, 2),
    )

    assert resultat["n_requetes"] == 2
    assert resultat["n_references"] == 3
    assert resultat["mrr"] == pytest.approx(0.75)
    assert resultat["par_k"]["1"]["rappel_micro"] == pytest.approx(1 / 3)
    assert resultat["par_k"]["1"]["rappel_macro"] == pytest.approx(0.25)
    assert resultat["par_k"]["1"]["taux_requetes_avec_au_moins_un_hit"] == pytest.approx(0.5)
    assert resultat["par_k"]["2"]["rappel_micro"] == pytest.approx(2 / 3)
    assert resultat["par_k"]["2"]["rappel_macro"] == pytest.approx(0.75)


def test_metriques_dedoublonnent_le_classement_avant_le_rang():
    a = ("code_travail", "L1233-3")
    b = ("code_travail", "L1233-4")

    resultat = calculer_rappel([{b}], [[a, a, b]], k_values=(1, 2))

    assert resultat["mrr"] == pytest.approx(0.5)
    assert resultat["par_k"]["1"]["rappel_micro"] == 0.0
    assert resultat["par_k"]["2"]["rappel_micro"] == 1.0


def test_references_exigent_un_code_pour_eviter_les_collisions():
    with pytest.raises(ValueError, match="Code absent"):
        charger_references_dossier({"id": "sans-code", "must_cite": ["1240"]})


def test_audit_dataset_accepte_citation_copie_du_candidat():
    fait = "Mon employeur a supprime mon poste et m'a convoque." 
    texte_article = (
        "Le licenciement pour motif economique est effectue par un employeur "
        "pour un ou plusieurs motifs non inherents a la personne du salarie."
    )
    reponse = {
        "contexte": fait,
        "parties": [],
        "demandes": [],
        "problemes_juridiques": [],
        "citations": [{
            "code": "code_travail",
            "numero": "L. 1233-3",
            "extrait": texte_article[:100],
            "fichier": "dossier.pdf",
            "pages": [1],
        }],
    }
    ligne = {
        "conversations": [
            {"from": "human", "value": (
                f"=== DOSSIER CLIENT ===\n[dossier.pdf, page 1] {fait}\n"
                "=== ARTICLES DISPONIBLES ===\n"
                f"- code_travail L. 1233-3 : Le licenciement pour motif economique\n"
                "  est effectue par un employeur pour un ou plusieurs motifs non\n"
                "  inherents a la personne du salarie.\n"
                "=== DATE DE REFERENCE ===\n2025-01-01"
            )},
            {"from": "gpt", "value": json.dumps(reponse)},
        ]
    }

    resultat = verifier_ligne(
        ligne,
        1,
        {"id": "positif-1", "type": "positif_synthetique_non_verifie", "statut": "genere_auto_a_revoir"},
    )

    assert resultat["erreurs_structure"] == []
    assert resultat["n_candidats"] == 1
    assert resultat["controle_pertinence_juridique"] == "non_effectue"


def test_exemple_hors_domaine_peut_apprendre_la_reponse_vide():
    cible = {
        "article_id": "x",
        "code": "code_travail",
        "numero": "L. 1233-3",
        "texte": "Texte public d'exemple suffisamment long.",
    }
    ligne = _construire_conversation(
        "Je cherche une recette de soupe.",
        [cible],
        None,
        date(2025, 1, 1),
    )

    resultat = verifier_ligne(
        ligne,
        1,
        {"type": "hors_domaine_sans_reference_juridique", "statut": "genere_auto_a_revoir"},
    )

    cible_json = json.loads(ligne["conversations"][2]["value"])
    assert cible_json["citations"] == []
    assert resultat["erreurs_structure"] == []


def test_depot_lecture_seule_interdit_les_ecritures(tmp_path):
    chemin = tmp_path / "legi.sqlite"
    depot = DepotSQLite(chemin)
    depot._conn.close()

    lecture_seule = DepotSQLite(chemin, lecture_seule=True)
    try:
        assert lecture_seule.compter() == 0
        with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
            lecture_seule.vider()
    finally:
        lecture_seule._conn.close()


def test_depot_lecture_seule_ne_cree_pas_une_base_absente(tmp_path):
    chemin = tmp_path / "absente.sqlite"

    with pytest.raises(FileNotFoundError):
        DepotSQLite(chemin, lecture_seule=True)
    assert not chemin.exists()


def test_diagnostic_couverture_retrieval_separe_du_resultat_llm():
    attendues = {
        ("code_travail", "L1233-2"),
        ("code_travail", "L1233-1"),
    }
    candidates = {("code_travail", "L1233-2")}

    diagnostic = _diagnostic_couverture(attendues, candidates)

    assert diagnostic["references_must_cite_dans_candidats"] == [
        ["code_travail", "L1233-2"]
    ]
    assert diagnostic["references_must_cite_absentes_des_candidats"] == [
        ["code_travail", "L1233-1"]
    ]
    assert diagnostic["rappel_retrieval_must_cite"] == pytest.approx(0.5)


def test_diagnostic_recherche_conserve_les_candidats_fts5_et_ceux_transmis():
    hit_present = ResultatRechercheArticle(
        article_id="LEGIARTI000000000001",
        code="code_travail",
        numero="L. 1233-2",
        extrait="extrait",
        score=1.0,
    )
    hit_sans_version = ResultatRechercheArticle(
        article_id="LEGIARTI000000000002",
        code="code_travail",
        numero="L. 1233-1",
        extrait="extrait",
        score=0.5,
    )

    class FauxChercheur:
        def chercher(self, texte, limite=5):
            return [hit_present, hit_sans_version]

    class FauxDepot:
        def trouver_par_id(self, article_id, date_reference):
            numero = "L1233-2" if article_id.endswith("1") else "L1233-1"
            a_une_version = article_id.endswith("1")
            return SimpleNamespace(
                code=SimpleNamespace(value="code_travail"),
                numero=numero,
                version_a=lambda d: object() if a_une_version else None,
            )

    traceur = _ChercheurTrace(FauxChercheur())
    traceur.chercher("chunk 1", limite=5)
    pipeline = SimpleNamespace(
        analyseur=SimpleNamespace(chercheur=traceur, limite_articles=5),
        depot=FauxDepot(),
    )

    diagnostic = _diagnostic_recherche(
        pipeline,
        date(2025, 1, 1),
        {
            ("code_travail", "L1233-2"),
            ("code_travail", "L1233-1"),
        },
    )

    assert diagnostic["n_appels_recherche"] == 1
    assert len(diagnostic["candidats_fts5_par_chunk"][0]["candidats_fts5"]) == 2
    assert diagnostic["candidats_transmis_au_llm"] == [
        ["code_travail", "L1233-2"]
    ]
    assert diagnostic["rappel_retrieval_must_cite"] == pytest.approx(0.5)


def test_diagnostic_citations_indique_statut_et_presence_candidate():
    citation = Citation(
        code=CodeJuridique.CODE_TRAVAIL,
        numero="L. 1233-3",
        date_reference=date(2025, 1, 1),
        extrait="texte",
    )
    verification = SimpleNamespace(
        citation=citation,
        statut=StatutVerification.TEXTE_DIFFERENT,
        est_valide=False,
    )
    candidat = ("code_travail", "L1233-3")

    details, statuts = _diagnostic_citations(
        SimpleNamespace(verifications=[verification]), {candidat},
    )

    assert details == [{
        "code": "code_travail",
        "numero": "L. 1233-3",
        "statut_verification": "texte_different",
        "est_valide": False,
        "article_dans_candidats": True,
        "extrait_fourni": True,
    }]
    assert statuts == {"texte_different": 1}


def test_diagnostic_citations_ne_plante_pas_sur_un_numero_vide():
    citation = Citation(
        code=CodeJuridique.CODE_TRAVAIL,
        numero="",
        date_reference=date(2025, 1, 1),
        extrait="texte",
    )
    verification = SimpleNamespace(
        citation=citation,
        statut=StatutVerification.NUMERO_MANQUANT,
        est_valide=False,
    )

    details, statuts = _diagnostic_citations(
        SimpleNamespace(verifications=[verification]), set(),
    )

    assert details[0]["numero"] == ""
    assert details[0]["article_dans_candidats"] is False
    assert statuts == {"numero_manquant": 1}


def test_agregats_separent_recall_retrieval_des_citations_valides():
    resultats = [{
        "statut_execution": "ok",
        "references": [["code_travail", "L1233-2"]],
        "references_valides_trouvees": [],
        "references_must_cite_dans_candidats": [["code_travail", "L1233-2"]],
        "statuts_citations": {"texte_different": 1},
        "duree_s": 1.0,
    }]

    metriques = _calculer_agregats(resultats)

    assert metriques["rappel_micro_retrieval_must_cite"] == 1.0
    assert metriques["rappel_micro_must_cite"] == 0.0
    assert metriques["statuts_citations"] == {"texte_different": 1}
````


## Fichiers supplémentaires demandés pour le patch d’architecture

DeepSeek propose un changement qui touche le schéma de sortie, le prompt, l’analyseur et les tests du pipeline. Voici aussi leurs versions complètes actuelles, pour éviter de travailler sur des extraits périmés. Ce sont des instantanés locaux ; compare-les à tes propres changements avant de rédiger un patch.

### `beaume/application/schemas.py`

````python
"""Schemas JSON transmis a Ollama pour le constrained decoding.

Separe du generateur pour eviter un cycle d'import entre
beaume.application.analyse_dossier et beaume.adapters.generateur_ollama.
Le schema n'est pas une affaire d'adaptateur : c'est le contrat de
sortie de l'analyse.

Constats du 2026-10-16 sur dossier_gros_001 :
- "code" doit etre un enum : sinon Qwen colle le numero dedans
  ("code_travail L2282-2").
- "fichier" doit etre un enum SANS "" : si on laisse "" dans la
  liste, Qwen choisit "" pour toutes les citations. Si on retire
  "", Qwen est force de choisir un vrai fichier.
- "pages" doit etre un enum des pages REELLES : avec un simple
  "type: integer", Qwen invente "1234", "5678", etc. en concatenant
  des numeros.
"""
from __future__ import annotations

import copy
from typing import Any

from beaume.legal.model import CodeJuridique

_CODES_VALIDES: list[str] = [c.value for c in CodeJuridique]


SCHEMA_ANALYSE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "contexte": {"type": "string"},
        "parties": {"type": "array", "items": {"type": "string"}},
        "demandes": {"type": "array", "items": {"type": "string"}},
        "problemes_juridiques": {
            "type": "array",
            "items": {"type": "string"},
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "enum": _CODES_VALIDES,
                    },
                    "numero": {"type": "string"},
                    "extrait": {"type": "string"},
                    "pages": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "fichier": {"type": "string"},
                },
                "required": ["code", "numero"],
            },
        },
    },
    "required": ["contexte", "citations"],
}


def schema_analyse_avec_fichiers(
    fichiers: tuple[str, ...],
    pages_max: int = 1,
) -> dict[str, Any]:
    """Retourne une copie de SCHEMA_ANALYSE avec "fichier" enumere.

    - "fichier" : enum des vrais noms, sans "".
    - "pages" : enum des pages disponibles (1..pages_max), minItems 1.

    Si aucun fichier n'est fourni, on retourne SCHEMA_ANALYSE tel quel.
    """
    schema = copy.deepcopy(SCHEMA_ANALYSE)
    if not fichiers:
        return schema

    pages_valides = list(range(1, max(1, pages_max) + 1))

    item = schema["properties"]["citations"]["items"]
    item["properties"]["fichier"] = {
        "type": "string",
        "enum": list(fichiers),
    }
    item["properties"]["pages"] = {
        "type": "array",
        "items": {"type": "integer", "enum": pages_valides},
        "minItems": 1,
    }
    item["required"] = ["code", "numero", "fichier", "pages", "extrait"]
    return schema
````

### `beaume/application/prompts.py`

````python
"""Construction des prompts envoyes au LLM.

Principes de conception (2026-10-16) :
- Prompt COURT (~400 tokens) : Qwen 7B decroche apres ~750 tokens.
- DOSSIER D'ABORD, regles ensuite : les petits modeles respectent
  mieux les instructions placees en fin de contexte.
- PAS D'EXEMPLE JSON dans le prompt : Qwen 7B recopie l'exemple au
  lieu de lire le dossier (bug identifie le 2026-10-16).
- Le JSON est force par le mode `format` d'Ollama (schema), pas par
  le prompt.
- "fichier" et "pages" sont contraints par le schema (enum sur les
  vrais noms et sur les pages reelles). Qwen met "" partout sinon.
- "fichier" et "pages" localisent le FAIT du dossier, PAS l'extrait
  de loi (corrige le 2026-10-18 : la consigne precedente demandait
  de recopier le fichier d'ou venait l'extrait de loi, ce qui etait
  contradictoire avec la regle 5 et poussait le modele a citer
  n'importe quel fichier du dossier).
"""
from datetime import date

from beaume.legal.model import Article


INSTRUCTION_SYSTEME = """Tu es un assistant juridique francais.

Tu produis UNIQUEMENT un objet JSON. Pas de texte avant. Pas de
texte apres. Pas de commentaire.

REGLES (dans l'ordre d'importance) :

1. Le "contexte" resume LE DOSSIER CI-DESSOUS. Tu ne recopies JAMAIS
   une phrase d'exemple. Tu decris les faits reels du dossier.

2. Tu ne cites QUE les articles fournis dans ARTICLES DISPONIBLES.
   Tu n'inventes JAMAIS un article, un numero ou un texte de loi.

3. "code" = UNIQUEMENT le nom du code, choisi dans la liste
   autorisee (par exemple "code_travail", "code_civil"). Ne mets
   JAMAIS le numero dans "code".

4. "numero" = UNIQUEMENT le numero de l'article (par exemple
   "L. 1235-3"). Ne mets JAMAIS le nom du code dans "numero".

5. "extrait" = COPIE LITTERALE d'une phrase de l'article, mot pour
   mot. Jamais de reformulation. Si tu ne peux pas copier exactement,
   ne cite pas l'article.

6. "fichier" = OBLIGATOIRE. Choisis un nom exact dans la LISTE DES
   FICHIERS ci-dessus. "fichier" et "pages" localisent le FAIT du
   dossier qui justifie la citation, PAS l'extrait de loi. Le
   dossier contient des en-tetes comme
   "[bulletins_salaire.pdf, page 1]" avant chaque paragraphe.
   Choisis le fichier et la page ou figure le fait concerne.
   Ne mets JAMAIS "".

7. "pages" = OBLIGATOIRE. Liste non vide de numeros de page, choisis
   parmi les entiers presents dans les en-tetes [nom.pdf, page X].
   Ne mets JAMAIS []."""


def _formater_articles(articles: list[Article], date_ref: date) -> str:
    lignes = []
    for a in articles:
        v = a.version_a(date_ref)
        if v is None:
            continue
        lignes.append(f"- {a.code.value} {a.numero} : {v.texte}")
    return "\n".join(lignes) if lignes else "(aucun article disponible)"


def _formater_liste_fichiers(fichiers: tuple[str, ...]) -> str:
    if not fichiers:
        return "(aucun fichier)"
    return "\n".join(f"- {nom}" for nom in fichiers)


def construire_prompt(
    texte_dossier: str,
    articles: list[Article],
    date_reference: date,
    fichiers_disponibles: tuple[str, ...] = (),
) -> str:
    """Construit le prompt dans l'ordre :
    1. Instructions systeme (courtes)
    2. Liste des fichiers du dossier
    3. Dossier client (avec en-tetes [fichier, page X])
    4. Articles disponibles
    5. Date de reference
    """
    articles_formates = _formater_articles(articles, date_reference)
    fichiers_formates = _formater_liste_fichiers(fichiers_disponibles)
    return (
        f"{INSTRUCTION_SYSTEME}\n\n"
        f"=== LISTE DES FICHIERS DU DOSSIER ===\n"
        f"{fichiers_formates}\n\n"
        f"=== DOSSIER CLIENT ===\n"
        f"{texte_dossier}\n\n"
        f"=== ARTICLES DISPONIBLES ===\n"
        f"{articles_formates}\n\n"
        f"=== DATE DE REFERENCE ===\n"
        f"{date_reference.isoformat()}\n\n"
        f"=== REPONSE (JSON uniquement) ===\n"
    )
````

### `beaume/application/analyse_dossier.py`

````python
"""Orchestrateur : analyse complete d'un dossier client."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from beaume.application.lecteur_dossier import LecteurDossier
from beaume.application.prompts import construire_prompt
from beaume.application.schemas import schema_analyse_avec_fichiers
from beaume.application.selecteur_chunks import SelecteurChunks
from beaume.legal.analyse import Analyse
from beaume.legal.model import Citation, CodeJuridique
from beaume.ports.chercheur_articles import ChercheurArticles
from beaume.ports.depot_articles import DepotArticles
from beaume.ports.generateur import Generateur
from beaume.ports.registre import RegistreExtracteurs
from beaume.utils.logging import get_logger

log = get_logger("analyse_dossier")


class ErreurAnalyse(Exception):
    """Le LLM n'a pas produit une sortie exploitable."""


def _extraire_json(texte: str) -> dict:
    if not texte:
        raise ErreurAnalyse("Reponse LLM vide")

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texte, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    debut = texte.find("{")
    fin = texte.rfind("}")
    if debut >= 0 and fin > debut:
        try:
            return json.loads(texte[debut:fin + 1])
        except json.JSONDecodeError as e:
            raise ErreurAnalyse(f"JSON invalide : {e}") from e

    raise ErreurAnalyse("Aucun JSON trouve dans la reponse LLM")


def _separer_code_et_numero(
    code_brut: str, numero_brut: str,
) -> tuple[str, str]:
    """Filet si le LLM colle code et numero dans le meme champ."""
    code_brut = code_brut.strip()
    numero_brut = numero_brut.strip()
    if " " not in code_brut:
        return code_brut, numero_brut

    prefixe, _, reste = code_brut.partition(" ")
    try:
        CodeJuridique(prefixe)
    except ValueError:
        return code_brut, numero_brut

    if not numero_brut:
        numero_brut = reste.strip()
    return prefixe, numero_brut


def _parse_analyse(brut: dict, date_reference: date) -> Analyse:
    citations_brutes = brut.get("citations", [])

    if isinstance(citations_brutes, list):
        log.info(
            "Reponse LLM : cles=%r, %d citations brutes",
            sorted(brut.keys()),
            len(citations_brutes),
        )
    else:
        log.warning(
            "Champ 'citations' de type inattendu : %s",
            type(citations_brutes).__name__,
        )

    citations = []
    for index, c in enumerate(citations_brutes, start=1):
        if not isinstance(c, dict):
            log.warning(
                "Citation %d ignoree : type=%s",
                index, type(c).__name__,
            )
            continue
        try:
            pages_brutes = c.get("pages", [])
            pages = tuple(
                int(p) for p in pages_brutes
                if isinstance(p, (int, float, str)) and str(p).isdigit()
            )
            code_brut, numero_brut = _separer_code_et_numero(
                str(c["code"]), str(c.get("numero", "")),
            )
            citations.append(
                Citation(
                    code=CodeJuridique(code_brut),
                    numero=numero_brut,
                    date_reference=date_reference,
                    extrait=c.get("extrait"),
                    pages=pages,
                    fichier=str(c.get("fichier", "")),
                )
            )
        except (KeyError, ValueError) as e:
            log.warning(
                "Citation %d ignoree (%s) : code=%r, message=%s",
                index, type(e).__name__, c.get("code"), e,
            )

    return Analyse(
        contexte=str(brut.get("contexte", "")),
        parties=[str(x) for x in brut.get("parties", [])],
        demandes=[str(x) for x in brut.get("demandes", [])],
        problemes_juridiques=[str(x) for x in brut.get("problemes_juridiques", [])],
        citations=citations,
        date_reference=date_reference,
    )


def _valider_provenance(
    analyse: Analyse,
    fichiers_disponibles: set[str],
    pages_par_fichier: dict[str, set[int]],
) -> Analyse:
    """Filet de securite sur la provenance des citations.

    Avec le schema enumere, ce filtre ne devrait plus s'exercer. Il
    reste en place pour les cas ou le decodage contraint serait
    contourne.

    Regles :
    - fichier vide    -> pages videes.
    - fichier inconnu -> fichier="" et pages=().
    - fichier valide  -> pages filtree sur les pages reelles du fichier.
      Si plus aucune page ne reste, on vide les pages.
    """
    citations: list[Citation] = []
    for index, c in enumerate(analyse.citations, start=1):
        nom = (c.fichier or "").strip()
        if not nom:
            if c.pages:
                log.warning(
                    "Citation %d : fichier absent, pages videes", index,
                )
                c = c.model_copy(update={"pages": ()})
        elif nom not in fichiers_disponibles:
            log.warning(
                "Citation %d : fichier inconnu, provenance effacee", index,
            )
            c = c.model_copy(update={"fichier": "", "pages": ()})
        else:
            pages_ok = pages_par_fichier.get(nom, set())
            pages_filtrees = tuple(p for p in c.pages if p in pages_ok)
            if pages_filtrees != c.pages:
                log.warning(
                    "Citation %d : pages invalides filtrees (%s -> %s)",
                    index, c.pages, pages_filtrees,
                )
                c = c.model_copy(update={"pages": pages_filtrees})
        citations.append(c)
    return analyse.model_copy(update={"citations": citations})


class AnalyseDossier:
    """Analyse complete d'un dossier client."""

    def __init__(
        self,
        registre: RegistreExtracteurs,
        chercheur: ChercheurArticles,
        generateur: Generateur,
        depot: DepotArticles,
        selecteur: SelecteurChunks | None = None,
        taille_chunk: int = 600,
        chevauchement: int = 80,
        limite_articles: int = 5,
    ) -> None:
        self.lecteur = LecteurDossier(
            registre,
            taille_chunk=taille_chunk,
            chevauchement=chevauchement,
        )
        self.chercheur = chercheur
        self.generateur = generateur
        self.depot = depot
        self.selecteur = selecteur or SelecteurChunks()
        self.limite_articles = limite_articles

    def _enrichir_articles(self, resultats, date_reference: date) -> list:
        """Recupere les Article complets depuis le depot a la date de reference."""
        vus: dict[str, object] = {}
        for r in resultats:
            if r.article_id in vus:
                continue
            article = self.depot.trouver_par_id(r.article_id, date_reference)
            if article is not None:
                vus[r.article_id] = article
        return list(vus.values())

    def analyser(
        self,
        dossier: Path,
        date_reference: date,
    ) -> Analyse:
        dossier = Path(dossier)
        resultat = self.lecteur.lire(dossier)

        all_chunks = []
        chunks_texte = []
        fichiers_ignores: list[str] = []
        fichiers_lus: list[str] = []
        pages_par_fichier: dict[str, set[int]] = {}
        for fichier in resultat.fichiers:
            if not fichier.ok:
                fichiers_ignores.append(fichier.chemin.name)
                log.warning(
                    "Fichier ignore (%s) : %s",
                    fichier.chemin.name,
                    fichier.erreur,
                )
                continue
            fichiers_lus.append(fichier.chemin.name)
            for chunk in fichier.chunks:
                all_chunks.append(chunk)
                chunks_texte.append(chunk.texte)
                pages_par_fichier.setdefault(
                    fichier.chemin.name, set(),
                ).update(
                    range(chunk.page_debut, chunk.page_fin + 1),
                )

        if not chunks_texte:
            log.warning("Aucun chunk exploitable dans %s", dossier)
            return Analyse(
                date_reference=date_reference,
                erreur="Aucun fichier exploitable dans le dossier",
                fichiers_ignores=tuple(fichiers_ignores),
            )

        pages_max = max(
            (max(p) for p in pages_par_fichier.values() if p),
            default=1,
        )

        selection = self.selecteur.selectionner(all_chunks)
        texte_dossier = self.selecteur.formater_pour_prompt(selection)

        resultats_recherche = []
        for chunk in chunks_texte:
            resultats_recherche.extend(
                self.chercheur.chercher(chunk, limite=self.limite_articles)
            )

        articles_candidats = self._enrichir_articles(
            resultats_recherche, date_reference,
        )
        log.info(
            "Analyse %s : %d chunks, %d articles candidats (%d hits chercheur)",
            dossier, len(chunks_texte), len(articles_candidats),
            len(resultats_recherche),
        )

        prompt = construire_prompt(
            texte_dossier,
            articles_candidats,
            date_reference,
            fichiers_disponibles=tuple(fichiers_lus),
        )

        schema = schema_analyse_avec_fichiers(
            tuple(fichiers_lus), pages_max=pages_max,
        )

        reponse = self.generateur.generer(
            prompt, temperature=0.0, format=schema,
        )
        log.info(
            "LLM %s : %d tokens reponse en %.2f s",
            reponse.modele,
            reponse.tokens_reponse or 0,
            reponse.duree_s,
        )

        try:
            brut = _extraire_json(reponse.texte)
        except ErreurAnalyse as e:
            log.error("Reponse LLM illisible : %s", type(e).__name__)
            # Diagnostic local : un debut de reponse permet de distinguer
            # une sortie tronquee (boucle) d'un JSON mal place. Le contenu
            # reste sur la machine, comme toute l'analyse.
            apercu = (reponse.texte or "")[:800]
            log.warning(
                "Debut de reponse (%d caracteres au total) : %r",
                len(reponse.texte or ""),
                apercu,
            )
            return Analyse(
                date_reference=date_reference,
                erreur=f"Reponse LLM illisible : {type(e).__name__}",
                fichiers_ignores=tuple(fichiers_ignores),
            )

        analyse = _parse_analyse(brut, date_reference)
        analyse = _valider_provenance(
            analyse, set(fichiers_lus), pages_par_fichier,
        )
        if fichiers_ignores:
            analyse = analyse.model_copy(
                update={"fichiers_ignores": tuple(fichiers_ignores)}
            )
        return analyse
````

### `beaume/adapters/generateur_ollama.py`

````python
"""Adaptateur Ollama pour la generation de texte (LLM local).

Respecte le contrat Generateur. Utilise un modele local via Ollama.
Aucune donnee ne quitte la machine.

Mode JSON natif : Ollama supporte le constrained decoding. Le schema
JSON est defini dans beaume.application.schemas et transmis via le
parametre `format`. Cet adaptateur ne connait pas la structure du
schema : il passe ce qu'on lui donne.

Correctifs du 2026-10-18 contre les boucles de generation :

1. num_predict (plafond dur) : empeche une generation de durer 20 minutes.
   La valeur 1536 laisse assez de marge pour 5 citations courtes.

2. repeat_penalty + repeat_last_n (anti-repetition) : empeche le modele
   de repeter le meme token ou la meme sequence. C'est le correctif de
   fond. Sans lui, le modele peut boucler jusqu'a epuisement du budget
   num_predict, produisant un JSON tronque et inutilisable.
   La valeur 1.15 avec une fenetre de 256 tokens est la convention
   documentee pour les petits modeles quantifies (Qwen2.5-3B inclus).
   Elle casse les boucles sans alterer la qualite du texte normal.

3. frequency_penalty + presence_penalty (penalites complementaires) :
   rendent les tokens deja utilises moins attractifs, ce qui renforce
   l'anti-repetition sur les longues sequences JSON.

Le couple num_predict + repeat_penalty est la defense minimale
recommandee. L'un sans l'autre est insuffisant : num_predict seul coupe
tard, repeat_penalty seul peut laisser le modele divaguer longuement
sans boucler.
"""
from __future__ import annotations

import time
from typing import Any

import ollama

from beaume.application.schemas import SCHEMA_ANALYSE
from beaume.ports.generateur import ReponseLLM
from beaume.utils.logging import get_logger

log = get_logger("generateur_ollama")

_MODELE_PAR_DEFAUT = "qwen-beaume-v1"

# Plafond dur de generation. Empeche une boucle de durer 20 minutes.
_NUM_PREDICT_PAR_DEFAUT = 1536

# Anti-repetition. 1.0 = desactive, > 1.0 = penalise les tokens recents.
# 1.15 est la valeur conventionnelle pour casser les boucles des petits
# modeles quantifies sans degrader le texte normal.
_REPEAT_PENALTY_PAR_DEFAUT = 1.15
_REPEAT_LAST_N_PAR_DEFAUT = 256

# Penalites complementaires pour renforcer l'anti-repetition sur les
# longues sequences JSON. 0.0 = desactive.
_FREQUENCY_PENALTY_PAR_DEFAUT = 0.2
_PRESENCE_PENALTY_PAR_DEFAUT = 0.1

# Reexport pour compatibilite : certains tests importent SCHEMA_ANALYSE
# depuis ce module. La definition vit dans beaume.application.schemas.
__all__ = ["GenerateurOllama", "SCHEMA_ANALYSE"]


class GenerateurOllama:
    """Generateur de texte via Ollama, 100% local."""

    def __init__(
        self,
        modele: str = _MODELE_PAR_DEFAUT,
        keep_alive: str = "24h",
        schema: dict[str, Any] | None = None,
        num_predict: int = _NUM_PREDICT_PAR_DEFAUT,
        repeat_penalty: float = _REPEAT_PENALTY_PAR_DEFAUT,
        repeat_last_n: int = _REPEAT_LAST_N_PAR_DEFAUT,
        frequency_penalty: float = _FREQUENCY_PENALTY_PAR_DEFAUT,
        presence_penalty: float = _PRESENCE_PENALTY_PAR_DEFAUT,
    ) -> None:
        if num_predict <= 0:
            raise ValueError("num_predict doit etre strictement positif")
        if repeat_penalty < 1.0:
            raise ValueError("repeat_penalty doit etre >= 1.0 (1.0 = desactive)")
        if repeat_last_n < 0:
            raise ValueError("repeat_last_n doit etre >= 0")
        self.modele = modele
        self.keep_alive = keep_alive
        self.schema = schema
        self.num_predict = num_predict
        self.repeat_penalty = repeat_penalty
        self.repeat_last_n = repeat_last_n
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty

    def nom_modele(self) -> str:
        return self.modele

    def generer(
        self,
        prompt: str,
        temperature: float = 0.0,
        format: dict[str, Any] | str | None = None,
    ) -> ReponseLLM:
        debut = time.perf_counter()

        # Priorite : format explicite > schema instance > rien.
        format_final = format if format is not None else self.schema

        options: dict[str, Any] = {
            "temperature": temperature,
            "num_predict": self.num_predict,
            "repeat_penalty": self.repeat_penalty,
            "repeat_last_n": self.repeat_last_n,
        }
        # Les penalites de frequence/presence ne sont pas supportees
        # par toutes les versions d'Ollama ; on ne les ajoute que si
        # elles sont non nulles.
        if self.frequency_penalty > 0.0:
            options["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty > 0.0:
            options["presence_penalty"] = self.presence_penalty

        kwargs: dict[str, Any] = {
            "model": self.modele,
            "prompt": prompt,
            "options": options,
            "keep_alive": self.keep_alive,
        }
        if format_final is not None:
            kwargs["format"] = format_final

        reponse = ollama.generate(**kwargs)
        duree = time.perf_counter() - debut

        texte = reponse.get("response", "")
        tokens_prompt = reponse.get("prompt_eval_count")
        tokens_reponse = reponse.get("eval_count")

        log.info(
            "Generation %s : %d tokens prompt, %d tokens reponse, %.2f s",
            self.modele,
            tokens_prompt or 0,
            tokens_reponse or 0,
            duree,
        )
        if tokens_reponse and tokens_reponse >= self.num_predict:
            log.warning(
                "Generation %s tronquee a num_predict=%d : le modele n'a pas "
                "produit de fin naturelle. Sortie possiblement en boucle.",
                self.modele,
                self.num_predict,
            )

        return ReponseLLM(
            texte=texte,
            modele=self.modele,
            duree_s=duree,
            tokens_prompt=tokens_prompt,
            tokens_reponse=tokens_reponse,
        )
````

### `tests/unit/test_pipeline_verification.py`

````python
"""Verifie que le pipeline rejette bien les citations problematiques.

Couvre trois trous identifies le 2026-10-18 :
1. EXTRAIT_MANQUANT via le pipeline (et pas seulement le verificateur).
2. TEXTE_DIFFERENT via le pipeline (extrait invente).
3. Le prompt ne contient plus l'ancienne consigne contradictoire.

Ces tests utilisent PipelineAnalyse, pas AnalyseDossier.analyser() seul,
car le pipeline est le point d'entree qui branche le verificateur.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pymupdf

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.application.prompts import construire_prompt
from beaume.legal.model import StatutVerification
from beaume.ports.generateur import ReponseLLM
from beaume.ports.registre import RegistreExtracteurs


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"


class FauxChercheur:
    def chercher(self, texte, limite=5):
        return []


class FauxGenerateur:
    def __init__(self, reponse: str) -> None:
        self._reponse = reponse

    def generer(self, prompt: str, temperature: float = 0.0, format=None) -> ReponseLLM:
        return ReponseLLM(
            texte=self._reponse,
            modele="faux-test",
            duree_s=0.001,
        )

    def nom_modele(self) -> str:
        return "faux-test"


def _make_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()


def _registre() -> RegistreExtracteurs:
    r = RegistreExtracteurs()
    r.enregistrer(ExtracteurPDF())
    return r


def _construire_pipeline(tmp_path: Path, reponse_llm: str) -> PipelineAnalyse:
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    depot.enregistrer(SourceFichierLocal(FIXTURE).charger())
    verificateur = VerificateurStandard(depot)
    return PipelineAnalyse(
        registre=_registre(),
        chercheur=FauxChercheur(),
        generateur=FauxGenerateur(reponse_llm),
        depot=depot,
        verificateur=verificateur,
    )


def test_pipeline_citation_sans_extrait_est_rejetee(tmp_path):
    """Une citation valide sur l'article 1240 mais sans extrait doit etre
    rejetee par le pipeline au statut EXTRAIT_MANQUANT."""
    _make_pdf(tmp_path / "lettre.pdf", "Le salarie conteste son licenciement.")

    reponse = (
        '{"contexte": "Test.", "citations": ['
        '{"code": "code_civil", "numero": "1240"}'
        ']}'
    )
    pipeline = _construire_pipeline(tmp_path, reponse)
    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_rejetees) == 1
    assert len(rapport.citations_valides) == 0
    assert rapport.citations_rejetees[0].statut == StatutVerification.EXTRAIT_MANQUANT


def test_pipeline_citation_avec_extrait_vide_est_rejetee(tmp_path):
    """Un extrait vide (espaces) doit aussi donner EXTRAIT_MANQUANT."""
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")

    reponse = (
        '{"contexte": "Test.", "citations": ['
        '{"code": "code_civil", "numero": "1240", "extrait": "   "}'
        ']}'
    )
    pipeline = _construire_pipeline(tmp_path, reponse)
    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_rejetees) == 1
    assert rapport.citations_rejetees[0].statut == StatutVerification.EXTRAIT_MANQUANT


def test_pipeline_citation_avec_extrait_invente_est_rejetee(tmp_path):
    """Un extrait qui ne figure pas dans l'article 1240 doit donner
    TEXTE_DIFFERENT, pas VALIDE."""
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")

    reponse = (
        '{"contexte": "Test.", "citations": ['
        '{"code": "code_civil", "numero": "1240", '
        '"extrait": "phrase completement inventee qui n existe pas"}'
        ']}'
    )
    pipeline = _construire_pipeline(tmp_path, reponse)
    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_rejetees) == 1
    assert rapport.citations_rejetees[0].statut == StatutVerification.TEXTE_DIFFERENT


def test_pipeline_citation_avec_extrait_correct_est_valide(tmp_path):
    """Contre-epreuve : extrait correct -> VALIDE, aucun rejet."""
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")

    reponse = (
        '{"contexte": "Test.", "citations": ['
        '{"code": "code_civil", "numero": "1240", '
        '"extrait": "qui cause a autrui un dommage"}'
        ']}'
    )
    pipeline = _construire_pipeline(tmp_path, reponse)
    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_valides) == 1
    assert len(rapport.citations_rejetees) == 0


def test_prompt_ne_contient_plus_ancienne_consigne_fichier():
    """Regression : l'ancienne phrase demandait de recopier le fichier
    d'ou venait l'extrait de loi, en contradiction avec la regle 5.
    Elle doit rester absente du prompt."""
    prompt = construire_prompt("dossier test", [], date(2024, 1, 1))

    assert "Recopie le nom du fichier d'ou vient l'extrait" not in prompt
    assert "PAS l'extrait de loi" in prompt
    assert "localisent le FAIT" in prompt
````


## Réponse prête à transmettre à DeepSeek — complément du 19 octobre 2026

Tu peux utiliser ce complément avec les instantanés complets des fichiers inclus plus haut. Le JSON du benchmark conservé dans `data/logs/` ne contient volontairement pas le texte brut des extraits ; j’ai relancé localement les trois cas synthétiques pour obtenir les aperçus ci-dessous. Aucun document client n’a été utilisé.

### Position sur l’architecture proposée

Je suis d’accord pour étudier en priorité la sélection d’un article candidat suivie de l’hydratation de son texte officiel par l’application. Je veux que tu prépares un patch ciblé et que tu expliques les tests avant que je le colle dans le dépôt. Le gain annoncé de `1/6` à `4/6` est une **hypothèse**, pas un résultat : il faudra relancer le même benchmark après application.

Quelques conditions à respecter dans la conception :

1. Fais sélectionner au modèle un identifiant de candidat stable (`article_id` Légifrance, ou un identifiant interne explicitement lié à cet ID), plutôt qu’un couple code/numéro libre. Le code doit vérifier par appartenance stricte que cet identifiant figure dans la liste réellement fournie au prompt. Un enum dans le schéma aide, mais la validation déterministe côté application reste obligatoire.
2. L’application récupère elle-même l’article et sa version à `date_reference`, puis fournit le texte officiel au rapport. Ne fais pas confiance au modèle pour générer le texte de loi.
3. Garde `VerificateurStandard` comme dernier contrôle. L’hydratation peut éviter les extraits inventés par le modèle, mais elle ne rend pas inutiles la vérification de date, du statut `ABROGE`, de la présence dans le corpus et des invariants de provenance.
4. Si le modèle ne sélectionne aucun candidat, représente explicitement l’absence de sélection. Ne construis pas une citation vide qui serait ensuite prise pour un article absent.
5. Pour un extrait court, précise comment l’application le choisit exactement dans le texte officiel. Renvoyer l’article entier est sûr pour l’exactitude textuelle mais peut être trop long ; un passage déterministe ou un identifiant de passage peut être une meilleure première version. Ne réintroduis pas une citation libre du LLM sans la vérifier.
6. Ajoute des tests : identifiant hors candidats rejeté avant le vérificateur ; identifiant connu hydraté avec la version à la date ; texte affiché identique à la source SQLite ; aucune sélection gérée sans exception ; aucun changement de comportement de `ABROGE` et `VERSION_INCORRECTE`.

Les résultats observés soutiennent cette piste : les trois citations `texte_different` portent sur des articles présents parmi les candidats. Cela ne prouve cependant pas encore que le patch ferait passer le rappel à `4/6`.

### 1. État Git réellement relevé

`git log -1 --oneline` :

```text
359a6bf feat: architecture stricte (JSON/Enums), validation de provenance, scripts de génération de dataset et ROADMAP
```

`git status --short --branch` :

```text
## main...origin/main
 M .gitignore
 M beaume/adapters/depot_sqlite.py
 M beaume/adapters/generateur_ollama.py
 M beaume/adapters/verificateur_standard.py
 M beaume/application/analyse_dossier.py
 M beaume/application/prompts.py
 M beaume/application/schemas.py
 M beaume/bench/dossiers_test.json
 M beaume/legal/model.py
 M beaume/ports/depot_articles.py
 M scripts/bench_qualite.py
 M scripts/bench_recherche.py
 M scripts/construire_dataset_entrainement.py
 M scripts/generer_dataset_ft.py
 M scripts/telecharger_corpus_v2.py
 M scripts/verifier_dataset.py
 M tests/unit/test_verificateur_citations.py
?? beaume/bench/__init__.py
?? beaume/bench/metriques.py
?? docs/AUDIT_RECHERCHE.md
?? docs/PASSATION_DEEPSEEK_2026-10-19.md
?? tests/unit/test_benchmarks.py
?? tests/unit/test_construire_dataset_entrainement.py
?? tests/unit/test_pipeline_verification.py
```

`git diff --stat` :

```text
17 files changed, 1525 insertions(+), 541 deletions(-)
```

Ce résumé du diff n’inclut pas les nouveaux fichiers non suivis listés après `??`. Aucun commit ni push n’a été fait ; ne réinitialise pas et n’écrase pas ces changements.

### 2. Les trois cas `texte_different`

Ils proviennent d’une nouvelle exécution locale de `qwen-beaume-v1` sur les dossiers synthétiques, à température 0. Les aperçus sont exactement les 200 premiers caractères (ou moins si l’extrait est plus court), comme dans ta commande. Le benchmark principal n’enregistre que la longueur et le booléen `extrait_fourni`, pas les extraits bruts.

**BE-LECO-003** — `code_travail`, `L1233-3`, statut `texte_different`, présent parmi les candidats, extrait de 1 257 caractères :

```text
Constitue un licenciement pour motif économique le licenciement effectué par un employeur pour un ou plusieurs motifs non inhérents à la personne du salarié résultant d'une suppression ou transformati
```

**BE-LECO-004** — `code_travail`, `L1233-4`, statut `texte_different`, présent parmi les candidats, extrait de 287 caractères :

```text
Le reclassement s’effectue sur un emploi relevant de la même catégorie que celui qu’il occupe ou sur un emploi équivalent assorti d’une rémunération équivalente. A défaut, et sous réserve de l’accord
```

**BE-LECO-005** — `code_travail`, `L1233-5`, statut `texte_different`, présent parmi les candidats, extrait de 128 caractères :

```text
Les charges de famille, en particulier celles des parents isolés ; L’ancienneté de service dans l’établissement ou l’entreprise;
```

Les numéros attendus de ces trois dossiers étaient tous réellement candidats. Pour BE-LECO-002, ni L1233-1 ni L1233-2 n’étaient dans les cinq candidats transmis. Le benchmark ne suffit pas à valider les annotations `must_cite`, qui sont provisoires et non relues par un juriste.

### 3. Fichiers complets disponibles

Les instantanés complets sont inclus dans les sections précédentes de ce même document : `model.py`, `depot_articles.py`, `depot_sqlite.py`, `verificateur_standard.py`, `bench_qualite.py`, les tests associés, puis `schemas.py`, `prompts.py`, `analyse_dossier.py`, `generateur_ollama.py` et `test_pipeline_verification.py`. Ils reflètent le dépôt local relevé le 19 octobre ; certains contiennent des changements antérieurs à cet audit.

### 4. Format des prochaines modifications

Je préfère recevoir le **fichier complet final pour chaque fichier modifié**, car j’applique les changements manuellement par copier-coller. Pour les fichiers longs, commence par résumer le petit diff et les raisons, puis donne le fichier complet sans `...`, sans omission d’imports ni de fonctions. Si la limite de réponse l’exige, sépare les fichiers en messages clairement titrés avec leurs chemins. N’écris rien dans le dépôt et ne commit/push pas : donne-moi les fichiers ou le patch à appliquer, puis attends mes résultats de tests.

