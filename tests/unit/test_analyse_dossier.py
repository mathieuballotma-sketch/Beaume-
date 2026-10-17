"""Tests du pipeline d'analyse de dossier."""
from datetime import date
from pathlib import Path

import pymupdf
import pytest

from beaume.adapters.depot_sqlite import DepotSQLite
from beaume.adapters.extracteur_pdf import ExtracteurPDF
from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.application.analyse_dossier import (
    AnalyseDossier,
    ErreurAnalyse,
    _extraire_json,
    _parse_analyse,
)
from beaume.ports.generateur import ReponseLLM
from beaume.ports.registre import RegistreExtracteurs


class FauxChercheur:
    def __init__(self, resultats=None):
        self.resultats = resultats or []
        self.appels = []

    def chercher(self, texte, limite=5):
        self.appels.append((texte, limite))
        return self.resultats


class FauxGenerateur:
    def __init__(self, reponse: str) -> None:
        self._reponse = reponse
        self.appels = []
        self.dernier_format = None

    def generer(
        self,
        prompt: str,
        temperature: float = 0.0,
        format=None,
    ) -> ReponseLLM:
        self.appels.append((prompt, temperature))
        self.dernier_format = format
        return ReponseLLM(
            texte=self._reponse,
            modele="faux",
            duree_s=0.001,
            tokens_prompt=10,
            tokens_reponse=20,
        )

    def nom_modele(self) -> str:
        return "faux"


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


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"


def _depot_vide(tmp_path):
    depot = DepotSQLite(tmp_path / "legi.sqlite")
    depot.enregistrer(SourceFichierLocal(FIXTURE).charger())
    return depot


def test_extraire_json_nu():
    d = _extraire_json('{"a": 1}')
    assert d == {"a": 1}


def test_extraire_json_dans_markdown():
    d = _extraire_json('```json\n{"a": 1}\n```')
    assert d == {"a": 1}


def test_extraire_json_avec_texte_autour():
    d = _extraire_json('Voici la reponse : {"a": 1} Voila.')
    assert d == {"a": 1}


def test_extraire_json_vide():
    with pytest.raises(ErreurAnalyse):
        _extraire_json("")


def test_extraire_json_invalide():
    with pytest.raises(ErreurAnalyse):
        _extraire_json("pas de json ici")


def test_parse_analyse_complet():
    brut = {
        "contexte": "Un salarie a ete licencie.",
        "parties": ["M. Dupont", "SARL Exemple"],
        "demandes": ["Indemnisation"],
        "problemes_juridiques": ["Licenciement sans cause reelle"],
        "citations": [
            {
                "code": "code_travail",
                "numero": "L. 1232-1",
                "extrait": "Tout licenciement pour motif personnel...",
            }
        ],
    }
    a = _parse_analyse(brut, date(2024, 1, 1))
    assert a.contexte.startswith("Un salarie")
    assert len(a.citations) == 1
    assert a.citations[0].numero == "L. 1232-1"
    assert a.date_reference == date(2024, 1, 1)


def test_parse_analyse_citation_code_invalide_ignoree():
    brut = {
        "contexte": "",
        "citations": [
            {"code": "code_inexistant", "numero": "X"},
            {"code": "code_travail", "numero": "L. 1232-1"},
        ],
    }
    a = _parse_analyse(brut, date(2024, 1, 1))
    assert len(a.citations) == 1


def test_parse_analyse_minimal():
    a = _parse_analyse({}, date(2024, 1, 1))
    assert a.contexte == ""
    assert a.citations == []
    assert a.date_reference == date(2024, 1, 1)


def test_analyse_dossier_vide(tmp_path):
    gen = FauxGenerateur('{"contexte": "vide"}')
    a = AnalyseDossier(_registre(), FauxChercheur(), gen, _depot_vide(tmp_path))
    resultat = a.analyser(tmp_path, date(2024, 1, 1))
    assert resultat.est_vide() or resultat.contexte == "vide"
    assert len(gen.appels) == 0


def test_analyse_dossier_avec_un_pdf(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Le salarie conteste son licenciement.")

    reponse_json = '{"contexte": "Un salarie conteste son licenciement.", "parties": ["Le salarie"], "demandes": ["Contestation"], "problemes_juridiques": ["Motif"], "citations": []}'
    gen = FauxGenerateur(reponse_json)
    a = AnalyseDossier(_registre(), FauxChercheur(), gen, _depot_vide(tmp_path))
    resultat = a.analyser(tmp_path, date(2024, 1, 1))

    assert "conteste" in resultat.contexte
    assert len(resultat.parties) == 1
    assert len(gen.appels) == 1


def test_analyse_dossier_reponse_illisible(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Contenu quelconque.")
    gen = FauxGenerateur("Je ne sais pas repondre.")
    a = AnalyseDossier(_registre(), FauxChercheur(), gen, _depot_vide(tmp_path))
    resultat = a.analyser(tmp_path, date(2024, 1, 1))
    assert resultat.est_vide()


def test_analyse_dossier_prompt_contient_date(tmp_path):
    _make_pdf(tmp_path / "lettre.pdf", "Test.")
    gen = FauxGenerateur('{"contexte": ""}')
    a = AnalyseDossier(_registre(), FauxChercheur(), gen, _depot_vide(tmp_path))
    a.analyser(tmp_path, date(2024, 6, 15))
    prompt, _ = gen.appels[0]
    assert "2024-06-15" in prompt
    assert "ARTICLES DISPONIBLES" in prompt


def test_analyse_dossier_chercheur_appele_par_chunk(tmp_path):
    _make_pdf(tmp_path / "a.pdf", "Contenu A suffisamment long pour un chunk.")
    chercheur = FauxChercheur()
    gen = FauxGenerateur('{"contexte": ""}')
    a = AnalyseDossier(_registre(), chercheur, gen, _depot_vide(tmp_path))
    a.analyser(tmp_path, date(2024, 1, 1))
    assert len(chercheur.appels) >= 1


def test_analyse_dossier_schema_enumere_les_fichiers(tmp_path):
    """Le schema transmis au generateur doit contenir les fichiers extraits."""
    _make_pdf(tmp_path / "lettre.pdf", "Contenu.")
    gen = FauxGenerateur('{"contexte": ""}')
    a = AnalyseDossier(_registre(), FauxChercheur(), gen, _depot_vide(tmp_path))
    a.analyser(tmp_path, date(2024, 1, 1))

    assert gen.dernier_format is not None
    item = gen.dernier_format["properties"]["citations"]["items"]
    assert "enum" in item["properties"]["fichier"]
    assert "lettre.pdf" in item["properties"]["fichier"]["enum"]
    assert "fichier" in item["required"]
    assert "pages" in item["required"]