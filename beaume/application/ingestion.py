"""Pipeline d'ingestion d'un dossier client.

Relie les briques : LecteurDossier -> Encodeur -> IndexVectoriel.
Toutes les dependances sont INJECTEES (loi 4).
"""
from dataclasses import dataclass
from pathlib import Path

from beaume.application.lecteur_dossier import (
    LecteurDossier,
    ResultatDossier,
)
from beaume.ports.encodeur import Encodeur
from beaume.ports.index_vectoriel import ElementIndexe, IndexVectoriel
from beaume.ports.registre import RegistreExtracteurs
from beaume.utils.logging import get_logger
from beaume.utils.profiler import chronometre

log = get_logger("ingestion")


@dataclass(frozen=True)
class RapportIngestion:
    chemin_dossier: Path
    nb_fichiers_ok: int
    nb_fichiers_erreur: int
    nb_chunks_total: int
    nb_chunks_indexes: int


def _identifiant_chunk(chemin_relatif: str, index_chunk: int) -> str:
    return f"{chemin_relatif}#chunk_{index_chunk}"


class IngestionDossier:
    """Ingere un dossier client dans un index vectoriel."""

    def __init__(
        self,
        registre: RegistreExtracteurs,
        encodeur: Encodeur,
        index: IndexVectoriel,
        taille_chunk: int = 600,
        chevauchement: int = 80,
    ) -> None:
        self.lecteur = LecteurDossier(
            registre,
            taille_chunk=taille_chunk,
            chevauchement=chevauchement,
        )
        self.encodeur = encodeur
        self.index = index

    @chronometre("ingestion.totale")
    def ingerer(self, dossier: Path) -> RapportIngestion:
        dossier = Path(dossier)
        resultat: ResultatDossier = self.lecteur.lire(dossier)

        chunks_a_indexer: list[tuple[str, str, dict]] = []
        for fichier in resultat.fichiers:
            if not fichier.ok:
                continue
            chemin_relatif = str(fichier.chemin.relative_to(dossier))
            for chunk in fichier.chunks:
                id_ = _identifiant_chunk(chemin_relatif, chunk.index)
                meta = {
                    "source": chemin_relatif,
                    "index_chunk": chunk.index,
                    "debut_car": chunk.debut_car,
                    "fin_car": chunk.fin_car,
                    "longueur": chunk.longueur,
                }
                chunks_a_indexer.append((id_, chunk.texte, meta))

        nb_total = len(chunks_a_indexer)
        if nb_total == 0:
            log.info("Aucun chunk a indexer")
            return RapportIngestion(
                chemin_dossier=dossier,
                nb_fichiers_ok=resultat.nb_ok,
                nb_fichiers_erreur=resultat.nb_erreurs,
                nb_chunks_total=0,
                nb_chunks_indexes=0,
            )

        textes = [t for (_id, t, _meta) in chunks_a_indexer]
        vecteurs = self.encodeur.encoder(textes)
        if len(vecteurs) != len(textes):
            raise RuntimeError(
                f"Encodeur incoherent : {len(textes)} textes, "
                f"{len(vecteurs)} vecteurs"
            )

        elements = [
            ElementIndexe(
                id=id_,
                vecteur=tuple(v),
                metadonnees=meta,
            )
            for (id_, _texte, meta), v in zip(chunks_a_indexer, vecteurs)
        ]
        self.index.ajouter(elements)

        log.info(
            "Ingestion terminee : %d fichiers, %d chunks indexes",
            resultat.nb_ok, len(elements),
        )

        return RapportIngestion(
            chemin_dossier=dossier,
            nb_fichiers_ok=resultat.nb_ok,
            nb_fichiers_erreur=resultat.nb_erreurs,
            nb_chunks_total=nb_total,
            nb_chunks_indexes=len(elements),
        )
