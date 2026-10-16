"""Orchestrateur : analyse complete d'un dossier client."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from beaume.application.lecteur_dossier import LecteurDossier
from beaume.application.prompts import construire_prompt
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


def _parse_analyse(brut: dict, date_reference: date) -> Analyse:
    citations_brutes = brut.get("citations", [])
    citations = []
    for c in citations_brutes:
        try:
            citations.append(
                Citation(
                    code=CodeJuridique(c["code"]),
                    numero=str(c["numero"]),
                    date_reference=date_reference,
                    extrait=c.get("extrait"),
                )
            )
        except (KeyError, ValueError) as e:
            # Ne pas loguer le contenu de `c` : il vient du LLM, donc
            # indirectement du dossier client. Le type d'erreur suffit.
            log.warning("Citation ignoree : %s", type(e).__name__)

    return Analyse(
        contexte=str(brut.get("contexte", "")),
        parties=[str(x) for x in brut.get("parties", [])],
        demandes=[str(x) for x in brut.get("demandes", [])],
        problemes_juridiques=[str(x) for x in brut.get("problemes_juridiques", [])],
        citations=citations,
        date_reference=date_reference,
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
        """Recupere les Article complets depuis le depot a la date de reference.

        Dedoublonne par article_id. La date determine la version de
        l'article : c'est celle du dossier, pas une date arbitraire.
        """
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
        nb_fichiers_ignores = 0
        for fichier in resultat.fichiers:
            if not fichier.ok:
                nb_fichiers_ignores += 1
                log.warning(
                    "Fichier ignore (%s) : %s",
                    fichier.chemin.name,
                    fichier.erreur,
                )
                continue
            for chunk in fichier.chunks:
                all_chunks.append(chunk)
                chunks_texte.append(chunk.texte)

        if nb_fichiers_ignores:
            log.warning(
                "Analyse partielle : %d fichier(s) non lu(s) sur %d",
                nb_fichiers_ignores,
                len(resultat.fichiers),
            )

        if not chunks_texte:
            log.warning("Aucun chunk exploitable dans %s", dossier)
            return Analyse(date_reference=date_reference)

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
            texte_dossier, articles_candidats, date_reference,
        )

        reponse = self.generateur.generer(prompt, temperature=0.0)
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
            return Analyse(date_reference=date_reference)

        return _parse_analyse(brut, date_reference)