"""Démonstration technique autonome ; données et réponse entièrement fictives.

Aucun modèle, corpus téléchargé ni accès réseau. N'évalue pas un LLM.
"""
import argparse
from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf

from beaume.adapters.chercheur_articles_fts5 import ChercheurArticlesFTS5
from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.legal.ids import IdentifiantLegifrance
from beaume.legal.model import Article, CodeJuridique, StatutVersion, VersionArticle
from beaume.ports.generateur import ReponseLLM
from beaume.ports.registre import RegistreExtracteurs


class GenerateurDemonstration:
    """Réponse fixe, explicitement sans intelligence ni validation juridique."""

    def nom_modele(self) -> str:
        return "demonstration-fixe-sans-LLM"

    def generer(self, prompt, temperature=0.0, format=None):
        return ReponseLLM(
            texte=json.dumps({
                "contexte": "DEMONSTRATION FICTIVE : dommage à un vélo fictif.",
                "citations": [{"article_id": "LEGIARTI000000000001",
                               "fichier": "exemple.pdf", "pages": [1]}],
            }),
            modele=self.nom_modele(), duree_s=0.0,
        )


def executer_demo(sortie: Path) -> None:
    if sortie.exists():
        raise FileExistsError("La sortie existe déjà ; choisir un nouveau chemin.")
    with TemporaryDirectory(prefix="beaume-demo-") as temp:
        root = Path(temp)
        dossier = root / "pieces"
        dossier.mkdir()
        with pymupdf.open() as pdf:
            page = pdf.new_page()
            page.insert_text((72, 72), "CAS FICTIF : dommage au velo de Camille. Aucune personne reelle.")
            pdf.save(dossier / "exemple.pdf")
        identifiant = IdentifiantLegifrance(valeur="LEGIARTI000000000001")
        depot = DepotSQLite(root / "corpus-fictif.sqlite")
        depot.enregistrer([Article(
            id=identifiant, code=CodeJuridique.CODE_CIVIL, numero="9999",
            versions=[VersionArticle(
                article_id=identifiant, numero="9999", date_debut=date(2020, 1, 1),
                date_fin=None, texte="REGLE FICTIVE DE TEST : dommage au velo fictif.",
                statut=StatutVersion.EN_VIGUEUR, source="demonstration_fictive_non_juridique",
            )],
        )])
        registre = RegistreExtracteurs()
        registre.enregistrer(ExtracteurPDF())
        pipeline = PipelineAnalyse(
            registre, ChercheurArticlesFTS5(depot), GenerateurDemonstration(),
            depot, VerificateurStandard(depot),
        )
        rapport, markdown = pipeline.executer(dossier, date(2024, 1, 1))
        if len(rapport.citations_valides) != 1:
            raise RuntimeError("Le parcours technique de démonstration a échoué.")
        sortie.parent.mkdir(parents=True, exist_ok=True)
        with sortie.open("x", encoding="utf-8") as f:
            f.write("# Démonstration technique — aucune valeur juridique\n\n"
                    "Corpus, référence et réponse fictifs. Aucun modèle n'a été évalué.\n\n")
            f.write(markdown)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sortie", type=Path, default=Path("data/out/demo_hors_ligne.md"))
    args = parser.parse_args()
    executer_demo(args.sortie)
    print(f"Démonstration écrite : {args.sortie}")


if __name__ == "__main__":
    main()
