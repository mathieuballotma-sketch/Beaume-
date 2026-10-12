"""Tests de l'adaptateur Hugging Face LEGI.

On utilise le vrai dataset (limite a 50 articles) pour valider
la mecanique. Le dataset est dans data/legal/legi_2025/.
"""
from pathlib import Path
import pytest

from beaume.adapters.source_huggingface_legi import SourceHuggingFaceLegi
from beaume.legal.mapping_codes import code_depuis_titre
from beaume.legal.model import CodeJuridique, StatutVersion
from beaume.ports.source_legale import SourceLegale


DATASET = Path(__file__).parent.parent.parent / "data" / "legal" / "legi_2025"
DATASET_EXISTE = DATASET.exists()


# ---------------------------------------------------------------------------
# Tests unitaires (ne dependent pas du dataset)
# ---------------------------------------------------------------------------

def test_mapping_code_civil():
    assert code_depuis_titre("Code civil") == CodeJuridique.CODE_CIVIL


def test_mapping_code_travail():
    assert code_depuis_titre("Code du travail") == CodeJuridique.CODE_TRAVAIL


def test_mapping_code_inconnu():
    assert code_depuis_titre("Code inconnu") == CodeJuridique.CODE_AUTRE
    assert code_depuis_titre(None) == CodeJuridique.CODE_AUTRE
    assert code_depuis_titre("") == CodeJuridique.CODE_AUTRE


def test_adaptateur_respecte_contrat():
    src = SourceHuggingFaceLegi(DATASET)
    assert isinstance(src, SourceLegale)


def test_description_contient_chemin():
    src = SourceHuggingFaceLegi(DATASET)
    assert "legi_2025" in src.description()


def test_description_avec_filtres():
    src = SourceHuggingFaceLegi(
        DATASET,
        codes_inclus={CodeJuridique.CODE_CIVIL},
        limite=10,
    )
    desc = src.description()
    assert "1 codes" in desc
    assert "limite 10" in desc


def test_fichier_absent(tmp_path):
    src = SourceHuggingFaceLegi(tmp_path / "absent")
    with pytest.raises(FileNotFoundError):
        src.charger()


# ---------------------------------------------------------------------------
# Tests d'integration (dependent du dataset telecharge)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not DATASET_EXISTE, reason="Dataset non telecharge")
def test_charge_50_articles():
    src = SourceHuggingFaceLegi(DATASET, limite=50)
    articles = src.charger()
    assert len(articles) == 50


@pytest.mark.skipif(not DATASET_EXISTE, reason="Dataset non telecharge")
def test_articles_ont_bon_type():
    src = SourceHuggingFaceLegi(DATASET, limite=10)
    articles = src.charger()
    for a in articles:
        assert a.id is not None
        assert isinstance(a.code, CodeJuridique)
        assert len(a.versions) >= 1
        assert a.versions[0].statut == StatutVersion.EN_VIGUEUR
        assert a.versions[0].source == "dila"


@pytest.mark.skipif(not DATASET_EXISTE, reason="Dataset non telecharge")
def test_filtre_code_civil():
    src = SourceHuggingFaceLegi(
        DATASET,
        codes_inclus={CodeJuridique.CODE_CIVIL},
        limite=20,
    )
    articles = src.charger()
    assert len(articles) > 0
    for a in articles:
        assert a.code == CodeJuridique.CODE_CIVIL


@pytest.mark.skipif(not DATASET_EXISTE, reason="Dataset non telecharge")
def test_filtre_code_travail():
    src = SourceHuggingFaceLegi(
        DATASET,
        codes_inclus={CodeJuridique.CODE_TRAVAIL},
        limite=20,
    )
    articles = src.charger()
    assert len(articles) > 0
    for a in articles:
        assert a.code == CodeJuridique.CODE_TRAVAIL


@pytest.mark.skipif(not DATASET_EXISTE, reason="Dataset non telecharge")
def test_article_civil_a_du_texte():
    src = SourceHuggingFaceLegi(
        DATASET,
        codes_inclus={CodeJuridique.CODE_CIVIL},
        limite=5,
    )
    articles = src.charger()
    for a in articles:
        assert a.versions[0].texte.strip() != ""


@pytest.mark.skipif(not DATASET_EXISTE, reason="Dataset non telecharge")
def test_dates_parsees():
    src = SourceHuggingFaceLegi(DATASET, limite=10)
    articles = src.charger()
    for a in articles:
        v = a.versions[0]
        assert v.date_debut is not None
        # La sentinelle 2999 doit devenir None
        if v.date_fin is not None:
            assert v.date_fin.year < 2999
