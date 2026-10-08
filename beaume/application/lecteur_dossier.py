"""Parcours d'un dossier client et extraction de tous ses fichiers.

Cet objet ne connait AUCUN format concret : il demande au registre.
C'est l'application de la loi d'inversion des dependances.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from beaume.application.chunker import Chunk, decouper
from beaume.application.etats import EtatDocument
from beaume.application.machine import Document, TransitionIllegale
from beaume.ports.registre import RegistreExtracteurs
from beaume.utils.logging import get_logger

log = get_logger("lecteur_dossier")


@dataclass(frozen=True)
class FichierExtrait:
    chemin: Path
    texte: str
    chunks: tuple[Chunk, ...] = ()
    erreur: str | None = None

    @property
    def ok(self) -> bool:
        return self.erreur is None


@dataclass
class ResultatDossier:
    chemin_dossier: Path
    debut: datetime
    fin: datetime | None = None
    fichiers: list[FichierExtrait] = field(default_factory=list)

    @property
    def nb_ok(self) -> int:
        return sum(1 for f in self.fichiers if f.ok)

    @property
    def nb_erreurs(self) -> int:
        return sum(1 for f in self.fichiers if not f.ok)

    @property
    def nb_chunks(self) -> int:
        return sum(len(f.chunks) for f in self.fichiers)


class LecteurDossier:
    """Lit un dossier client, extrait et decoupe chaque fichier."""

    def __init__(
        self,
        registre: RegistreExtracteurs,
        taille_chunk: int = 600,
        chevauchement: int = 80,
    ) -> None:
        self.registre = registre
        self.taille_chunk = taille_chunk
        self.chevauchement = chevauchement

    def lire(self, dossier: Path) -> ResultatDossier:
        dossier = Path(dossier)
        if not dossier.is_dir():
            raise NotADirectoryError(f"Dossier introuvable : {dossier}")

        resultat = ResultatDossier(
            chemin_dossier=dossier,
            debut=datetime.now(timezone.utc),
        )

        for fichier in sorted(dossier.iterdir()):
            if not fichier.is_file():
                continue
            if fichier.name.startswith("."):
                continue

            extracteur = self.registre.pour(fichier)
            if extracteur is None:
                log.info("Format non supporte : %s", fichier.name)
                resultat.fichiers.append(
                    FichierExtrait(
                        chemin=fichier,
                        texte="",
                        erreur=f"format non supporte : {fichier.suffix}",
                    )
                )
                continue

            doc = Document(chemin=fichier)
            try:
                doc.transition(EtatDocument.EXTRAIT, "extraction en cours")
                texte = extracteur.extraire(fichier)
                chunks = tuple(
                    decouper(texte, self.taille_chunk, self.chevauchement)
                )
                resultat.fichiers.append(
                    FichierExtrait(
                        chemin=fichier,
                        texte=texte,
                        chunks=chunks,
                    )
                )
                log.info(
                    "Extrait : %s (%d caracteres, %d chunks)",
                    fichier.name, len(texte), len(chunks),
                )
            except Exception as exc:  # noqa: BLE001
                log.error("Echec sur %s : %s", fichier.name, exc)
                try:
                    doc.echouer(str(exc))
                except TransitionIllegale:
                    pass
                resultat.fichiers.append(
                    FichierExtrait(chemin=fichier, texte="", erreur=str(exc))
                )

        resultat.fin = datetime.now(timezone.utc)
        return resultat
