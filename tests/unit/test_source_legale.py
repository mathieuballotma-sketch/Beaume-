"""Tests du port SourceLegale et de l'adaptateur SourceFichierLocal."""
from pathlib import Path
import json
import pytest

from beaume.adapters.source_fichier_local import SourceFichierLocal
from beaume.legal.model import CodeJuridique, StatutVersion
from beaume.ports.source_legale import SourceLegale


FIXTURE = Path(__file__).parent.parent / "fixtures" / "articles_test.json"


def test_adaptateur_respecte_contrat():
    assert isinstance(SourceFichierLocal(FIXTURE), SourceLegale)


def test_description_contient_chemin():
    src = SourceFichierLocal(FIXTURE)
    assert "articles_test.json" in src.description()


def test_fichier_absent(tmp_path):
    src = SourceFichierLocal(tmp_path / "absent.json")
    with pytest.raises(FileNotFoundError):
        src.charger()


def test_charge_deux_articles():
    src = SourceFichierLocal(FIXTURE)
    articles = src.charger()
    assert len(articles) == 2


def test_article_travail_bien_construit():
    src = SourceFichierLocal(FIXTURE)
    articles = src.charger()
    a = next(x for x in articles if x.code == CodeJuridique.CODE_TRAVAIL)
    assert a.numero == "L. 1234-1"
    assert len(a.versions) == 1
    assert a.versions[0].statut == StatutVersion.EN_VIGUEUR
    assert "contrat de travail" in a.versions[0].texte


def test_article_civil_bien_construit():
    src = SourceFichierLocal(FIXTURE)
    articles = src.charger()
    a = next(x for x in articles if x.code == CodeJuridique.CODE_CIVIL)
    assert a.numero == "1240"
    assert "dommage" in a.versions[0].texte


def test_article_versionne_date_detectee():
    src = SourceFichierLocal(FIXTURE)
    articles = src.charger()
    a = next(x for x in articles if x.numero == "1240")
    from datetime import date
    v = a.version_a(date(2020, 1, 1))
    assert v is not None
    assert "1240" == v.numero


def test_fichier_mal_forme_rejette(tmp_path):
    mauvais = tmp_path / "mauvais.json"
    mauvais.write_text('{"articles": "pas une liste"}', encoding="utf-8")
    src = SourceFichierLocal(mauvais)
    with pytest.raises(ValueError):
        src.charger()


def test_fichier_json_invalide(tmp_path):
    mauvais = tmp_path / "invalide.json"
    mauvais.write_text("{ceci n'est pas du json", encoding="utf-8")
    src = SourceFichierLocal(mauvais)
    with pytest.raises(json.JSONDecodeError):
        src.charger()