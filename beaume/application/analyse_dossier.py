"""Orchestrateur : analyse complete d'un dossier client.

Refonte du 2026-10-19 : le LLM ne produit plus (code, numero, extrait).
Il selectionne un article_id parmi les candidats fournis, et
l'application hydrate les champs de la Citation depuis SQLite. Voir
_hydrater_citation et _parse_analyse. Ce changement vise les
texte_different observes sur bench_qualite : le modele choisissait le
bon article mais recopiait un extrait qui n'existait pas dans le texte
officiel.

Correction du 2026-10-22 (option A) : ajout de la detection directe
des references explicites (_extraire_articles_directs), avec les
corrections issues de l'audit :
  - prefixes L/R/D preserves via normaliser_numero() ;
  - le motif n'attrape plus une annee seule (plus d'« article 2010 ») ;
  - le code est choisi par cle la plus longue en premier, dans le
    contexte le plus proche (plus de « procedure civile » lu comme
    « civil ») ;
  - PROVENANCE_INSUFFISANTE et les autres statuts non uniques ne sont
    plus injectes dans les candidats : ils restent visibles comme
    mentions non resolues.
"""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from beaume.application.lecteur_dossier import LecteurDossier
from beaume.application.prompts import construire_prompt
from beaume.application.schemas import schema_analyse_avec_candidats
from beaume.application.selecteur_chunks import SelecteurChunks
from beaume.legal.analyse import Analyse
from beaume.legal.model import Article, Citation, CodeJuridique
from beaume.legal.normalisation import normaliser_numero
from beaume.ports.chercheur_articles import ChercheurArticles
from beaume.ports.depot_articles import DepotArticles, ResultatRechercheArticle
from beaume.ports.generateur import Generateur
from beaume.ports.registre import RegistreExtracteurs
from beaume.ports.resolveur_articles import StatutResolution
from beaume.utils.logging import get_logger

log = get_logger("analyse_dossier")


_SENTINELLE_AUCUN_ARTICLE = "__AUCUN__"
_RRF_K = 60


# ---------------------------------------------------------------------------
# Detection des references explicites
# ---------------------------------------------------------------------------

# Formes acceptees :
#   - "article L.137-2", "articles L. 137-2", "article 2224" ;
#   - "L.137-2", "R.1234-1", "D.1234-1" sans le mot article ;
#   - "2224 du Code ..." (nombre suivi d'un code explicite).
#
# Les annees seules et les montants ne sont pas captures : la derniere
# alternative exige un contexte de code, les autres exigent "article"
# ou un prefixe L/R/D.
_PATTERN_ARTICLE = re.compile(
    r"\b(?:"
    r"articles?\s+(?:L\.?\s*|R\.?\s*|D\.?\s*)?\d+(?:-\d+)*"
    r"|L\.?\s*\d+(?:-\d+)*"
    r"|R\.?\s*\d+(?:-\d+)*"
    r"|D\.?\s*\d+(?:-\d+)*"
    r"|\d+(?:-\d+)*(?=\s+(?:du|de\s+la|des)\s+[Cc]ode\b)"
    r")\b",
    re.IGNORECASE,
)

# Trié par longueur décroissante pour que « procédure civile » passe
# avant « civil » et « procédure pénale » avant « pénal » (piège du
# sous-chaîne : « civil » est une sous-chaîne de « procédure civile »).
_CODES_PAR_LONGUEUR = sorted(
    [
        ("consommation", CodeJuridique.CODE_CONSOMMATION),
        ("civil", CodeJuridique.CODE_CIVIL),
        ("travail", CodeJuridique.CODE_TRAVAIL),
        ("commerce", CodeJuridique.CODE_COMMERCE),
        ("sécurité sociale", CodeJuridique.CODE_SECURITE_SOCIALE),
        ("urbanisme", CodeJuridique.CODE_URBANISME),
        ("environnement", CodeJuridique.CODE_ENVIRONNEMENT),
        ("pénal", CodeJuridique.CODE_PENAL),
        ("procédure civile", CodeJuridique.CODE_PROCEDURE_CIVILE),
        ("procédure pénale", CodeJuridique.CODE_PROCEDURE_PENALE),
    ],
    key=lambda kv: -len(kv[0]),
)

# Coupure de clause pour ne pas regarder au-delà de la référence
# immédiate : « du Code civil et l'article 2 du Code du travail » ne
# doit pas attribuer « travail » à l'article 1.
_CLAUSE_BREAK = re.compile(r"(?:\s+et\s+|\.\s|\n|;\s|\?\s|!\s)")


def _trouver_code_dans_contexte(
    texte: str, debut: int, fin: int
) -> CodeJuridique | None:
    """Code le plus proche et le plus specifique autour de la reference.

    Priorite :
    1. apres la reference, limite a la clause courante ;
    2. apres la reference, fenetre entiere (80 caracteres) ;
    3. avant la reference (80 caracteres).

    Le tri par longueur decroissante evite que « civil » masque
    « procedure civile ».
    """
    apres_brut = texte[fin:fin + 80].lower()
    m = _CLAUSE_BREAK.search(apres_brut)
    apres_clause = apres_brut[:m.start()] if m else apres_brut
    for nom, code in _CODES_PAR_LONGUEUR:
        if nom in apres_clause:
            return code
    for nom, code in _CODES_PAR_LONGUEUR:
        if nom in apres_brut:
            return code
    avant = texte[max(0, debut - 80):debut].lower()
    for nom, code in _CODES_PAR_LONGUEUR:
        if nom in avant:
            return code
    return None


class ErreurAnalyse(Exception):
    """Le LLM n'a pas produit une sortie exploitable."""


def _extraire_json(texte: str) -> dict:
    if not texte:
        raise ErreurAnalyse("Reponse LLM vide")

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texte, re.DOTALL)
    if match:
        try:
            resultat = json.loads(match.group(1))
            if not isinstance(resultat, dict):
                raise ErreurAnalyse("La racine JSON doit etre un objet")
            return resultat
        except json.JSONDecodeError:
            pass

    debut = texte.find("{")
    fin = texte.rfind("}")
    if debut >= 0 and fin > debut:
        try:
            resultat = json.loads(texte[debut:fin + 1])
            if not isinstance(resultat, dict):
                raise ErreurAnalyse("La racine JSON doit etre un objet")
            return resultat
        except json.JSONDecodeError as e:
            raise ErreurAnalyse(f"JSON invalide : {e}") from e

    raise ErreurAnalyse("Aucun JSON trouve dans la reponse LLM")


def _premiere_phrase(texte: str, longueur_max: int = 200) -> str:
    """Retourne la premiere phrase complete, ou un prefixe borne.

    L'extrait est construit de facon deterministe depuis le texte
    officiel. Il ne vient jamais du LLM. Une phrase complete (point
    suivi d'un espace ou d'un saut de ligne) est preferree ; sinon,
    on tronque proprement a longueur_max caracteres.
    """
    if not texte or longueur_max <= 0:
        return ""
    texte = texte.strip()
    for i, c in enumerate(texte):
        if c in ".!?":
            if i + 1 >= len(texte) or texte[i + 1] in " \n\t":
                # Ne pas prendre « 1. » dans une liste juridique pour
                # une fin de phrase.
                if c == "." and i > 0 and texte[i - 1].isdigit():
                    continue
                phrase = texte[: i + 1].strip()
                if len(phrase) <= longueur_max:
                    return phrase
                break
    if len(texte) <= longueur_max:
        return texte
    if longueur_max <= 3:
        return texte[:longueur_max]
    # Garde la longueur stricte, y compris les points de suspension.
    prefixe = texte[:max(1, longueur_max - 3)]
    fin_mot = prefixe.rfind(" ")
    if fin_mot > 0:
        prefixe = prefixe[:fin_mot]
    return prefixe.rstrip() + "..."


def _hydrater_citation(
    article_id: str,
    date_reference: date,
    fichier: str,
    pages: tuple[int, ...],
    depot: DepotArticles,
) -> Citation | None:
    """Construit une Citation a partir de l'article_id selectionne.

    Retourne None si l'article n'existe pas dans le corpus. Sinon,
    hydrate code et numero depuis l'Article et extrait depuis la
    version applicable a date_reference. Si aucune version n'est
    applicable, extrait reste vide ; le verificateur statuera
    (VERSION_INCORRECTE).
    """
    article = depot.trouver_par_id(article_id, date_reference)
    if article is None:
        return None
    version = article.version_a(date_reference)
    extrait = _premiere_phrase(version.texte) if version is not None else ""
    return Citation(
        code=article.code,
        numero=version.numero if version is not None else article.numero,
        date_reference=date_reference,
        extrait=extrait or None,
        pages=pages,
        fichier=fichier,
        article_id=article_id,
    )


def _parse_analyse(
    brut: dict,
    date_reference: date,
    depot: DepotArticles,
    candidats_par_id: set[str],
) -> Analyse:
    avertissements: list[str] = []

    def avertir(message: str) -> None:
        if message not in avertissements:
            avertissements.append(message)
        log.warning("%s", message)

    if not isinstance(brut, dict):
        return Analyse(
            date_reference=date_reference,
            erreur="Reponse JSON de type inattendu",
        )

    citations_brutes = brut.get("citations", [])

    if isinstance(citations_brutes, list):
        log.info(
            "Reponse LLM : cles=%r, %d citations brutes",
            sorted(brut.keys()),
            len(citations_brutes),
        )
    else:
        avertir("Champ citations invalide; les citations ont ete ignorees.")
        citations_brutes = []

    citations: list[Citation] = []
    for c in citations_brutes:
        if not isinstance(c, dict):
            avertir("Element de citation mal forme; il a ete ignore.")
            continue

        article_id = str(c.get("article_id", "")).strip()
        if not article_id or article_id == _SENTINELLE_AUCUN_ARTICLE:
            avertir("Citation ignoree: identifiant d'article absent.")
            continue
        if article_id not in candidats_par_id:
            avertir("Citation ignoree: article absent des candidats autorises.")
            continue

        pages_brutes = c.get("pages", [])
        pages: tuple[int, ...] = ()
        if isinstance(pages_brutes, list):
            pages_valides: list[int] = []
            for page in pages_brutes:
                if isinstance(page, bool):
                    continue
                if isinstance(page, int):
                    numero_page = page
                elif isinstance(page, str) and page.strip().isdigit():
                    numero_page = int(page.strip())
                else:
                    continue
                if numero_page > 0 and numero_page not in pages_valides:
                    pages_valides.append(numero_page)
            pages = tuple(pages_valides)
            if len(pages) != len(pages_brutes):
                avertir("Pages de provenance invalides ou dupliquees.")
            if len(pages) > 5:
                pages = pages[:5]
                avertir("Limite de cinq pages par citation depassee.")
        else:
            avertir("Pages de provenance absentes ou mal formees.")

        fichier_brut = c.get("fichier", "")
        fichier = fichier_brut.strip() if isinstance(fichier_brut, str) else ""
        if not fichier:
            avertir("Provenance documentaire absente pour une citation.")

        citation = _hydrater_citation(
            article_id=article_id,
            date_reference=date_reference,
            fichier=fichier,
            pages=pages,
            depot=depot,
        )
        if citation is None:
            avertir("Citation ignoree: article absent du corpus local.")
            continue
        citations.append(citation)

    contexte = brut.get("contexte", "")
    if not isinstance(contexte, str):
        contexte = ""
        avertir("Champ contexte invalide; resume omis.")

    def lire_liste(cle: str) -> list[str]:
        valeur = brut.get(cle, [])
        if not isinstance(valeur, list):
            avertir(f"Champ {cle} invalide; contenu omis.")
            return []
        elements = [item.strip() for item in valeur if isinstance(item, str)]
        if len(elements) != len(valeur):
            avertir(f"Elements invalides dans le champ {cle}; ignores.")
        return [element for element in elements if element]

    return Analyse(
        contexte=contexte.strip(),
        parties=lire_liste("parties"),
        demandes=lire_liste("demandes"),
        problemes_juridiques=lire_liste("problemes_juridiques"),
        citations=citations,
        date_reference=date_reference,
        avertissements=tuple(avertissements),
    )


def _valider_provenance(
    analyse: Analyse,
    fichiers_disponibles: set[str],
    pages_par_fichier: dict[str, set[int]],
) -> Analyse:
    """Filet de securite sur la provenance des citations.

    Regles inchangees :
    - fichier vide    -> pages videes.
    - fichier inconnu -> fichier="" et pages=().
    - fichier valide  -> pages filtree sur les pages reelles du fichier.
      Si plus aucune page ne reste, on vide les pages.
    """
    citations: list[Citation] = []
    provenance_invalide = False
    for index, c in enumerate(analyse.citations, start=1):
        nom = (c.fichier or "").strip()
        if not nom:
            provenance_invalide = True
            if c.pages:
                log.warning("Citation %d : fichier absent, pages videes", index)
                c = c.model_copy(update={"pages": ()})
        elif nom not in fichiers_disponibles:
            provenance_invalide = True
            log.warning("Citation %d : fichier inconnu, provenance effacee", index)
            c = c.model_copy(update={"fichier": "", "pages": ()})
        else:
            pages_ok = pages_par_fichier.get(nom, set())
            pages_filtrees = tuple(p for p in c.pages if p in pages_ok)
            if pages_filtrees != c.pages or not pages_filtrees:
                provenance_invalide = True
                log.warning("Citation %d : pages invalides filtrees", index)
                c = c.model_copy(update={"pages": pages_filtrees})
        citations.append(c)

    avertissements = list(analyse.avertissements)
    if provenance_invalide:
        message = (
            "La provenance fichier/page est absente ou invalide pour au "
            "moins une citation."
        )
        if message not in avertissements:
            avertissements.append(message)
    return analyse.model_copy(
        update={
            "citations": citations,
            "avertissements": tuple(avertissements),
        }
    )


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
        limite_articles: int = 10,
        limite_candidats: int = 10,
    ) -> None:
        if limite_articles <= 0:
            raise ValueError("limite_articles doit etre > 0")
        if limite_candidats <= 0:
            raise ValueError("limite_candidats doit etre > 0")
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
        self.limite_candidats = limite_candidats

    def _extraire_articles_directs(
        self, texte: str, date_reference: date
    ) -> tuple[list[Article], list[dict]]:
        """Detecte les references explicites dans le texte fourni.

        Retourne (articles_resolus, mentions_non_resolues).

        Seuls les statuts UNIQUE sont ajoutes a `articles_resolus` :
        ce sont les seuls candidats transmissibles au LLM. Les autres
        statuts (PROVENANCE_INSUFFISANTE, AMBIGUITE_*, REFERENCE_ABSENTE,
        AUCUNE_VERSION_A_LA_DATE, ERREUR_TECHNIQUE, ou absence de code
        dans le contexte) sont conserves dans `mentions_non_resolues`
        avec leur motif : visibles, jamais presentes comme applicables.

        La resolution exige un code explicite dans le contexte. Sans
        code identifiable, la mention n'est pas resolue : elle n'est
        pas devinee.
        """
        if not hasattr(self.depot, "resoudre_article"):
            log.info(
                "Resolution directe indisponible : le depot n'expose "
                "pas resoudre_article. Les references explicites ne "
                "sont pas resolues dans cette analyse."
            )
            return [], []

        articles_resolus: list[Article] = []
        mentions_non_resolues: list[dict] = []
        vus: set[str] = set()

        for match in _PATTERN_ARTICLE.finditer(texte):
            brut = match.group(0).strip()
            # Retire le mot "article" mais conserve le prefixe L/R/D.
            numero_brut = re.sub(
                r"^articles?\s+", "", brut, flags=re.IGNORECASE
            )
            numero = normaliser_numero(numero_brut)
            if not numero:
                continue

            code = _trouver_code_dans_contexte(
                texte, match.start(), match.end()
            )
            if code is None:
                mentions_non_resolues.append(
                    {
                        "reference_brute": brut,
                        "numero_normalise": numero,
                        "code": None,
                        "offset": match.start(),
                        "statut": "code_absent_du_contexte",
                        "motif": (
                            "Aucun code juridique explicite dans le "
                            "contexte de la reference."
                        ),
                    }
                )
                continue

            try:
                res = self.depot.resoudre_article(
                    code, numero, date_reference, strict=False
                )
            except Exception as e:
                log.debug(
                    "Erreur resolution directe %s %s : %s",
                    code, numero, e,
                )
                continue

            if res.statut == StatutResolution.UNIQUE and res.article_id_famille:
                article = self.depot.trouver_par_id(
                    res.article_id_famille, date_reference
                )
                if article is not None and article.id.valeur not in vus:
                    articles_resolus.append(article)
                    vus.add(article.id.valeur)
                continue

            mentions_non_resolues.append(
                {
                    "reference_brute": brut,
                    "numero_normalise": numero,
                    "code": (
                        code.value if hasattr(code, "value") else str(code)
                    ),
                    "offset": match.start(),
                    "statut": (
                        res.statut.value
                        if hasattr(res.statut, "value")
                        else str(res.statut)
                    ),
                    "motif": res.message or "",
                }
            )

        return articles_resolus, mentions_non_resolues

    def _enrichir_articles(
        self,
        resultats_par_chunk: Sequence[Sequence[ResultatRechercheArticle]],
        date_reference: date,
    ) -> list[Article]:
        """Classe les identifiants par RRF et hydrate un nombre borne.

        Le chercheur retourne jusqu'a N resultats par chunk. Sans limite
        globale, un dossier long peut produire des centaines d'identifiants
        dans le schema JSON et dans le prompt. Le Reciprocal Rank Fusion
        favorise les articles bien classes de facon repetee sans comparer
        directement des scores FTS issus de requetes differentes.
        """
        if not resultats_par_chunk:
            return []

        scores_rrf: dict[str, float] = {}
        for resultats in resultats_par_chunk:
            deja_vus_dans_chunk: set[str] = set()
            for rang, resultat in enumerate(resultats, start=1):
                article_id = resultat.article_id
                if not article_id or article_id in deja_vus_dans_chunk:
                    continue
                deja_vus_dans_chunk.add(article_id)
                scores_rrf[article_id] = (
                    scores_rrf.get(article_id, 0.0)
                    + 1.0 / (_RRF_K + rang)
                )

        ids_tries = sorted(
            scores_rrf,
            key=lambda identifiant: (
                -scores_rrf[identifiant],
                identifiant,
            ),
        )
        articles: list[Article] = []
        for article_id in ids_tries:
            article = self.depot.trouver_par_id(article_id, date_reference)
            if article is None or article.version_a(date_reference) is None:
                continue
            articles.append(article)
            if len(articles) >= self.limite_candidats:
                break
        return articles

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
                log.warning("Fichier ignore apres echec de lecture ou extraction")
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
            log.warning("Aucun chunk exploitable dans le dossier")
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

        # Detection directe sur le texte complet (pas seulement la
        # selection destinee au prompt) : une reference citee dans un
        # passage ecarte du prompt ne doit pas disparaitre.
        texte_complet = "\n".join(chunks_texte)
        articles_directs, mentions_non_resolues = (
            self._extraire_articles_directs(texte_complet, date_reference)
        )

        resultats_recherche_par_chunk = []
        for chunk in chunks_texte:
            resultats_recherche_par_chunk.append(
                self.chercheur.chercher(chunk, limite=self.limite_articles)
            )

        articles_fts5 = self._enrichir_articles(
            resultats_recherche_par_chunk, date_reference,
        )

        # Fusion : references directes d'abord (elles sont explicitement
        # citees dans les pieces), puis FTS5 sans doublon, plafonnees.
        ids_directs = {a.id.valeur for a in articles_directs}
        articles_candidats = (
            articles_directs
            + [a for a in articles_fts5 if a.id.valeur not in ids_directs]
        )[: self.limite_candidats]

        ids_candidats = tuple(a.id.valeur for a in articles_candidats)
        candidats_par_id = set(ids_candidats)
        nombre_hits = sum(len(groupe) for groupe in resultats_recherche_par_chunk)

        log.info(
            "Analyse dossier : %d chunks, %d articles candidats "
            "(%d directs, %d via FTS5, %d hits chercheur, "
            "%d mentions non resolues, limite globale=%d)",
            len(chunks_texte), len(articles_candidats),
            len(articles_directs), len(articles_fts5),
            nombre_hits, len(mentions_non_resolues), self.limite_candidats,
        )

        prompt = construire_prompt(
            texte_dossier,
            articles_candidats,
            date_reference,
            fichiers_disponibles=tuple(fichiers_lus),
        )

        schema = schema_analyse_avec_candidats(
            article_ids=ids_candidats,
            fichiers=tuple(fichiers_lus),
            pages_max=pages_max,
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
            log.warning(
                "Reponse LLM invalide (%d caracteres); contenu non journalise",
                len(reponse.texte or ""),
            )
            return Analyse(
                date_reference=date_reference,
                erreur=f"Reponse LLM illisible : {type(e).__name__}",
                fichiers_ignores=tuple(fichiers_ignores),
            )

        analyse = _parse_analyse(
            brut,
            date_reference=date_reference,
            depot=self.depot,
            candidats_par_id=candidats_par_id,
        )
        if not ids_candidats:
            message = (
                "Aucun article candidat n'a ete identifie (recherche et "
                "detection directe); aucune citation juridique ne pouvait "
                "etre selectionnee."
            )
            analyse = analyse.model_copy(
                update={"avertissements": (*analyse.avertissements, message)}
            )
        elif not analyse.citations and not analyse.avertissements:
            message = (
                "Aucun article n'a ete selectionne; cela ne prouve pas "
                "qu'aucun texte juridique ne s'applique."
            )
            analyse = analyse.model_copy(
                update={"avertissements": (*analyse.avertissements, message)}
            )
        if mentions_non_resolues:
            refs = ", ".join(
                m["reference_brute"] for m in mentions_non_resolues
            )
            message = (
                f"{len(mentions_non_resolues)} reference(s) explicite(s) "
                f"detectee(s) mais non resolue(s) : {refs}. Ces mentions "
                "ne sont pas des articles applicables ; elles restent "
                "visibles pour verification humaine."
            )
            analyse = analyse.model_copy(
                update={"avertissements": (*analyse.avertissements, message)}
            )
        analyse = _valider_provenance(
            analyse, set(fichiers_lus), pages_par_fichier,
        )
        if fichiers_ignores:
            analyse = analyse.model_copy(
                update={"fichiers_ignores": tuple(fichiers_ignores)}
            )
        return analyse