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