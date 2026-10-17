"""Tests du pipeline complet (analyse + verification + Markdown)."""
from datetime import date
from pathlib import Path

import pymupdf
import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.adapters.verificateur_standard import VerificateurStandard
from beaume.application.pipeline import PipelineAnalyse
from beaume.ports.generateur import ReponseLLM
from beaume.ports.registre import RegistreExtracteurs


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"


class FauxChercheur:
    def __init__(self, resultats=None):
        self.resultats = resultats or []

    def chercher(self, texte, limite=5):
        return self.resultats


class FauxGenerateur:
    def __init__(self, reponse: str) -> None:
        self._reponse = reponse
        self.dernier_format = None

    def generer(
        self,
        prompt: str,
        temperature: float = 0.0,
        format=None,
    ) -> ReponseLLM:
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


def _registre() -> RegistreExtracteurs:
    r = RegistreExtracteurs()
    r.enregistrer(ExtracteurPDF())
    return r


def _construire_pipeline(tmp_path, reponse_llm: str) -> PipelineAnalyse:
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


def test_pipeline_dossier_vide(tmp_path):
    pipeline = _construire_pipeline(tmp_path, '{"contexte": ""}')
    rapport, md = pipeline.executer(tmp_path, date(2024, 1, 1))
    assert "Rapport d'analyse" in md
    assert len(rapport.verifications) == 0


def test_pipeline_avec_citation_valide(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Le salarie conteste son licenciement.")
    reponse = '{"contexte": "Contestation.", "citations": [{"code": "code_civil", "numero": "1240", "extrait": "dommage"}]}'
    pipeline = _construire_pipeline(tmp_path, reponse)
    rapport, md = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_valides) == 1
    assert len(rapport.citations_rejetees) == 0
    assert "Articles applicables" in md
    assert "1240" in md


def test_pipeline_avec_citation_rejetee(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")
    reponse = '{"contexte": "Test.", "citations": [{"code": "code_civil", "numero": "9999"}]}'
    pipeline = _construire_pipeline(tmp_path, reponse)
    rapport, md = pipeline.executer(tmp_path, date(2024, 1, 1))

    assert len(rapport.citations_valides) == 0
    assert len(rapport.citations_rejetees) == 1
    assert "rejetees" in md


def test_pipeline_ecrit_fichier(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Un fait.")
    reponse = '{"contexte": "Test simple.", "citations": []}'
    pipeline = _construire_pipeline(tmp_path, reponse)
    sortie = tmp_path / "sortie" / "rapport.md"

    pipeline.executer(tmp_path, date(2024, 1, 1), chemin_sortie=sortie)

    assert sortie.exists()
    assert "Rapport d'analyse" in sortie.read_text(encoding="utf-8")


def test_pipeline_modele_llm_trace(tmp_path):
    pipeline = _construire_pipeline(tmp_path, '{"contexte": ""}')
    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))
    assert rapport.modele_llm == "faux-test"


def test_pipeline_duree_positive(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Peu importe.")
    pipeline = _construire_pipeline(tmp_path, '{"contexte": "x"}')
    rapport, _ = pipeline.executer(tmp_path, date(2024, 1, 1))
    assert rapport.duree_s >= 0