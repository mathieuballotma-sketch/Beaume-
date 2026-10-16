"""Selection des chunks pertinents par question.

Au lieu d'envoyer TOUT le dossier au LLM, on selectionne les chunks
les plus pertinents pour chaque question-cle :
    - faits
    - parties
    - demandes
    - problemes_juridiques

Methode : scoring par mots-cles ponderes, normalise par la longueur
du chunk (pour ne pas favoriser les chunks longs).

Fonction pure : aucune I/O, aucun appel reseau.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from beaume.application.chunker import Chunk


SIGNATURES: dict[str, dict[str, int]] = {
    "faits": {
        "survenu": 3, "date": 2, "suite": 2, "contexte": 2,
        "lorsque": 2, "depuis": 2, "fait": 2, "jour": 2,
        "convocation": 3, "entretien": 3, "decision": 2,
        "lettre": 3, "recu": 2, "informe": 2, "prealable": 3,
    },
    "parties": {
        "monsieur": 4, "madame": 4, "societe": 3, "salarie": 3,
        "employeur": 3, "demandeur": 3, "defendeur": 3,
        "sarl": 3, "sas": 3, "client": 2, "signe": 2,
        "demeurant": 3, "qualite": 2, "agent": 2,
    },
    "demandes": {
        "sollicite": 5, "demande": 4, "requiert": 4, "obtenir": 4,
        "souhaite": 4, "prie": 3, "contestation": 4, "contester": 4,
        "reparation": 3, "indemnisation": 4, "dommages": 3,
        "assistance": 3, "intervention": 3,
    },
    "problemes_juridiques": {
        "harcelement": 5, "licenciement": 5, "faute": 4, "manquement": 4,
        "violation": 4, "illegal": 3, "conflit": 3, "dommage": 3,
        "cause": 2, "serieuse": 3, "reelle": 3, "prejudice": 3,
        "discrimination": 5, "agissements": 4, "pressions": 4,
    },
}


_LONGUEUR_MIN = 3


def _normaliser(texte: str) -> str:
    """Minuscules, sans accents, ponctuation -> espace."""
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


def _score_question(texte_norm: str, signature: dict[str, int]) -> float:
    """Score d'un chunk pour une question.

    Somme ponderee des occurrences des mots-cles, divisee par la
    racine du nombre de mots (pour ne pas favoriser les gros chunks).
    """
    if not texte_norm:
        return 0.0
    mots = texte_norm.split()
    nb_mots = len(mots)
    if nb_mots == 0:
        return 0.0

    score = 0.0
    for mot, poids in signature.items():
        if mot in texte_norm:
            occurrences = texte_norm.count(mot)
            score += occurrences * poids

    return score / (nb_mots ** 0.5)


@dataclass(frozen=True)
class ChunkSelectionne:
    """Un chunk avec son score pour une question donnee."""
    chunk: Chunk
    question: str
    score: float


@dataclass
class SelectionChunks:
    """Resultat de la selection, avec tracabilite."""
    par_question: dict[str, list[ChunkSelectionne]]
    chunks_totaux: int
    chunks_utilises: int


class SelecteurChunks:
    """Selectionne les chunks pertinents pour chaque question."""

    def __init__(self, top_par_question: int = 3, score_min: float = 0.05):
        if top_par_question <= 0:
            raise ValueError("top_par_question doit etre > 0")
        if score_min < 0:
            raise ValueError("score_min doit etre >= 0")
        self.top = top_par_question
        self.score_min = score_min

    def selectionner(self, chunks: list[Chunk]) -> SelectionChunks:
        """Selectionne les chunks, chacun assigne a sa question dominante.

        Chaque chunk apparait dans UNE SEULE question : celle ou son
        score est le plus eleve. Puis on garde le top N par question.
        """
        if not chunks:
            return SelectionChunks(
                par_question={q: [] for q in SIGNATURES},
                chunks_totaux=0,
                chunks_utilises=0,
            )

        textes_norm = {c.index: _normaliser(c.texte) for c in chunks}

        par_question: dict[str, list[ChunkSelectionne]] = {
            q: [] for q in SIGNATURES
        }

        for chunk in chunks:
            scores = {
                q: _score_question(textes_norm[chunk.index], sig)
                for q, sig in SIGNATURES.items()
            }
            question_dom = max(scores, key=scores.get)
            score_dom = scores[question_dom]
            if score_dom > self.score_min:
                par_question[question_dom].append(
                    ChunkSelectionne(
                        chunk=chunk,
                        question=question_dom,
                        score=score_dom,
                    )
                )

        for q in par_question:
            par_question[q].sort(key=lambda x: -x.score)
            par_question[q] = par_question[q][: self.top]

        total_utilises = sum(len(v) for v in par_question.values())

        return SelectionChunks(
            par_question=par_question,
            chunks_totaux=len(chunks),
            chunks_utilises=total_utilises,
        )

    def formater_pour_prompt(self, selection: SelectionChunks) -> str:
        """Construit un texte structure pour le LLM.

        Chaque chunk est precede d'un en-tete `[fichier, page X]` pour
        que le LLM puisse citer la source dans sa reponse.
        """
        blocs = []
        for question in SIGNATURES:
            chunks = selection.par_question.get(question, [])
            if not chunks:
                continue
            titre = question.upper().replace("_", " ")
            blocs.append(f"=== {titre} ===")
            for sel in chunks:
                c = sel.chunk
                if c.fichier:
                    if c.page_debut == c.page_fin:
                        entete = f"[{c.fichier}, page {c.page_debut}]"
                    else:
                        entete = (
                            f"[{c.fichier}, pages "
                            f"{c.page_debut}-{c.page_fin}]"
                        )
                    blocs.append(entete)
                blocs.append(c.texte)
                blocs.append("")
        return "\n".join(blocs)
