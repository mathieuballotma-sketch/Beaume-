"""Regressions sur la selection par ID, l'hydratation et la provenance."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pymupdf

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.legal.model import ResultatVerification, StatutVerification
from beaume.ports.depot_articles import ResultatRechercheArticle
from beaume.ports.generateur import ReponseLLM
from beaume.ports.registre import RegistreExtracteurs


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"
ID_1240 = "LEGIARTI000033020517"


class FauxChercheur:
    def __init__(self, resultats=None):
        self.resultats = resultats if resultats is not None else [
            ResultatRechercheArticle(
                article_id=ID_1240,
                code="code_civil",
                numero="1240",
                extrait="article 1240",
                score=1.0,
            ),
        ]

    def chercher(self, texte, limite=5):
        return self.resultats[:limite]


class FauxGenerateur:
    def __init__(self, reponse: str) -> None:
        self._reponse = reponse
        self.dernier_format = None
        self.dernier_prompt = ""

    def generer(self, prompt: str, temperature: float = 0.0, format=None) -> ReponseLLM:
        self.dernier_prompt = prompt
        self.dernier_format = format
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


def _construire_pipeline(
    tmp_path: Path,
    reponse_llm: str,
    resultats=None,
    verificateur=None,
) -> tuple[PipelineAnalyse, FauxGenerateur]:
    depot = DepotSQLite(tmp_path / "_db" / "legi.sqlite")
    depot.enregistrer(SourceFichierLocal(FIXTURE).charger())
    registre = RegistreExtracteurs()
    registre.enregistrer(ExtracteurPDF())
    generateur = FauxGenerateur(reponse_llm)
    pipeline = PipelineAnalyse(
        registre=registre,
        chercheur=FauxChercheur(resultats),
        generateur=generateur,
        depot=depot,
        verificateur=verificateur or VerificateurStandard(depot),
    )
    return pipeline, generateur


def _citation(fichier="lettre.pdf", pages="[1]"):
    return (
        '{"article_id": "' + ID_1240 + '", '
        '"fichier": "' + fichier + '", "pages": ' + pages + '}'
    )


def test_pipeline_hydrate_le_texte_officiel_et_valide_la_citation(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Le salarie conteste son licenciement.")
    reponse = '{"contexte": "Test.", "citations": [' + _citation() + ']}'
    pipeline, generateur = _construire_pipeline(tmp_path, reponse)

    rapport, markdown = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_valides) == 1
    citation = rapport.citations_valides[0].citation
    assert citation.article_id == ID_1240
    assert citation.numero == "1240"
    assert citation.extrait.startswith("Tout fait quelconque")
    assert "Tout fait quelconque" in generateur.dernier_prompt
    assert "Articles applicables" in markdown


def test_pipeline_ignore_code_numero_et_extrait_fournis_par_le_llm(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Le salarie conteste son licenciement.")
    reponse = (
        '{"contexte": "Test.", "citations": [{'
        '"article_id": "' + ID_1240 + '", '
        '"code": "code_travail", "numero": "L9999", '
        '"extrait": "texte invente", '
        '"fichier": "lettre.pdf", "pages": [1]}]}'
    )
    pipeline, _ = _construire_pipeline(tmp_path, reponse)

    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_valides) == 1
    citation = rapport.citations_valides[0].citation
    assert citation.code.value == "code_civil"
    assert citation.numero == "1240"
    assert "invente" not in citation.extrait


def test_pipeline_rejette_un_identifiant_hors_candidats_et_marque_partiel(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")
    reponse = (
        '{"contexte": "Test.", "citations": [{'
        '"article_id": "LEGIARTI999999999999", '
        '"fichier": "lettre.pdf", "pages": [1]}]}'
    )
    pipeline, _ = _construire_pipeline(tmp_path, reponse)

    rapport, markdown = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert rapport.verifications == []
    assert rapport.analyse.etat == "PARTIEL"
    assert "article absent des candidats autorises" in " ".join(
        rapport.analyse.avertissements
    )
    assert "Etat** : PARTIEL" in markdown


def test_pipeline_sans_candidat_signale_le_defaut_de_recherche(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")
    pipeline, generateur = _construire_pipeline(
        tmp_path,
        '{"contexte": "Test.", "citations": []}',
        resultats=[],
    )

    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))

    item = generateur.dernier_format["properties"]["citations"]["items"]
    assert item["properties"]["article_id"]["enum"] == ["__AUCUN__"]
    assert rapport.analyse.etat == "PARTIEL"
    assert any("Aucun article candidat" in x for x in rapport.analyse.avertissements)


def test_pipeline_efface_page_inexistante_et_avertit(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")
    reponse = '{"contexte": "Test.", "citations": [' + _citation(pages="[99]") + ']}'
    pipeline, _ = _construire_pipeline(tmp_path, reponse)

    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_valides) == 1
    assert rapport.citations_valides[0].citation.pages == ()
    assert rapport.analyse.etat == "PARTIEL"
    assert any("provenance fichier/page" in x for x in rapport.analyse.avertissements)


def test_pipeline_marque_partiel_si_le_verificateur_rejette_une_citation(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")

    class VerificateurRejet:
        def verifier_toutes(self, citations):
            return [
                ResultatVerification(
                    statut=StatutVerification.ABROGE,
                    citation=citation,
                    message="Article abroge a cette date.",
                )
                for citation in citations
            ]

    reponse = '{"contexte": "Test.", "citations": [' + _citation() + ']}'
    pipeline, _ = _construire_pipeline(
        tmp_path,
        reponse,
        verificateur=VerificateurRejet(),
    )

    rapport, markdown = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_rejetees) == 1
    assert rapport.analyse.etat == "PARTIEL"
    assert any("verificateur juridique" in x for x in rapport.analyse.avertissements)
    assert "Avertissements" in markdown
