"""Pipeline complet : dossier -> analyse -> verification -> Markdown."""
import time
from datetime import date
from pathlib import Path

from beaume.application.analyse_dossier import AnalyseDossier
from beaume.output.rapport import Rapport, rendre_markdown
from beaume.ports.chercheur_articles import ChercheurArticles
from beaume.ports.depot_articles import DepotArticles
from beaume.ports.generateur import Generateur
from beaume.ports.registre import RegistreExtracteurs
from beaume.ports.verificateur_citations import VerificateurCitations
from beaume.utils.logging import get_logger
from beaume.utils.profiler import chronometre

log = get_logger("pipeline")


class PipelineAnalyse:
    """Orchestrateur haut niveau : dossier + date -> Markdown."""

    def __init__(
        self,
        registre: RegistreExtracteurs,
        chercheur: ChercheurArticles,
        generateur: Generateur,
        depot: DepotArticles,
        verificateur: VerificateurCitations,
    ) -> None:
        self.analyseur = AnalyseDossier(registre, chercheur, generateur)
        self.depot = depot
        self.verificateur = verificateur

    @chronometre("pipeline.total")
    def executer(
        self,
        dossier: Path,
        date_reference: date,
        chemin_sortie: Path | None = None,
    ) -> tuple[Rapport, str]:
        dossier = Path(dossier)
        log.info("Pipeline : %s au %s", dossier, date_reference)

        debut = time.perf_counter()
        analyse = self.analyseur.analyser(dossier, date_reference)
        verifications = self.verificateur.verifier_toutes(analyse.citations)
        duree = time.perf_counter() - debut

        rapport = Rapport(
            dossier=dossier,
            date_reference=date_reference,
            analyse=analyse,
            verifications=verifications,
            modele_llm=self.analyseur.generateur.nom_modele(),
            duree_s=duree,
        )
        markdown = rendre_markdown(rapport)

        log.info(
            "Pipeline termine : %d citations (%d valides, %d rejetees) en %.2f s",
            len(verifications),
            len(rapport.citations_valides),
            len(rapport.citations_rejetees),
            duree,
        )

        if chemin_sortie is not None:
            chemin_sortie = Path(chemin_sortie)
            chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
            chemin_sortie.write_text(markdown, encoding="utf-8")
            log.info("Markdown ecrit : %s", chemin_sortie)

        return rapport, markdown
