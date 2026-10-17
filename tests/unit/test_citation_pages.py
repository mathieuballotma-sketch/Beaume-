"""Verifie que les pages et fichiers sont lus et affiches, que la
provenance inventee par le LLM est effacee, que code/numero sont
bien separes, et que le schema enumere les fichiers disponibles."""
from __future__ import annotations

from datetime import date

from beaume.application.analyse_dossier import (
    _parse_analyse,
    _separer_code_et_numero,
    _valider_provenance,
)
from beaume.application.prompts import construire_prompt
from beaume.application.schemas import (
    SCHEMA_ANALYSE,
    schema_analyse_avec_fichiers,
)
from beaume.legal.analyse import Analyse
from beaume.legal.model import Citation, CodeJuridique


# --- _parse_analyse ---------------------------------------------------------


def test_parse_analyse_lit_pages_et_fichier():
    brut = {
        "contexte": "test",
        "citations": [{
            "code": "code_civil",
            "numero": "1240",
            "extrait": "test",
            "pages": [3, 4],
            "fichier": "conclusions.pdf",
        }],
    }
    analyse = _parse_analyse(brut, date(2024, 1, 1))
    assert len(analyse.citations) == 1
    c = analyse.citations[0]
    assert c.pages == (3, 4)
    assert c.fichier == "conclusions.pdf"


def test_parse_analyse_sans_pages():
    brut = {
        "contexte": "test",
        "citations": [{
            "code": "code_civil",
            "numero": "1240",
            "extrait": "test",
        }],
    }
    analyse = _parse_analyse(brut, date(2024, 1, 1))
    c = analyse.citations[0]
    assert c.pages == ()
    assert c.fichier == ""


def test_parse_analyse_separe_code_et_numero_colle():
    brut = {
        "contexte": "test",
        "citations": [{
            "code": "code_travail L2282-2",
            "numero": "",
            "extrait": "test",
        }],
    }
    analyse = _parse_analyse(brut, date(2024, 1, 1))
    assert len(analyse.citations) == 1
    c = analyse.citations[0]
    assert c.code == CodeJuridique.CODE_TRAVAIL
    assert c.numero == "L2282-2"


def test_parse_analyse_code_colle_garde_numero_existant():
    brut = {
        "contexte": "test",
        "citations": [{
            "code": "code_civil 1240",
            "numero": "1240",
            "extrait": "test",
        }],
    }
    analyse = _parse_analyse(brut, date(2024, 1, 1))
    c = analyse.citations[0]
    assert c.code == CodeJuridique.CODE_CIVIL
    assert c.numero == "1240"


# --- _separer_code_et_numero ------------------------------------------------


def test_separer_code_et_numero_code_simple():
    code, numero = _separer_code_et_numero("code_civil", "1240")
    assert code == "code_civil"
    assert numero == "1240"


def test_separer_code_et_numero_colle():
    code, numero = _separer_code_et_numero("code_travail L2282-2", "")
    assert code == "code_travail"
    assert numero == "L2282-2"


def test_separer_code_et_numero_prefixe_inconnu():
    code, numero = _separer_code_et_numero("code inconnu 1234", "")
    assert code == "code inconnu 1234"
    assert numero == ""


# --- schema Ollama ----------------------------------------------------------


def test_schema_analyse_enumere_les_codes():
    code_schema = (
        SCHEMA_ANALYSE["properties"]["citations"]["items"]
        ["properties"]["code"]
    )
    assert "enum" in code_schema
    assert "code_travail" in code_schema["enum"]
    assert "code_civil" in code_schema["enum"]


def test_schema_base_ne_contraint_pas_fichier():
    item = SCHEMA_ANALYSE["properties"]["citations"]["items"]
    assert "enum" not in item["properties"]["fichier"]
    assert "fichier" not in item["required"]
    assert "pages" not in item["required"]


def test_schema_analyse_avec_fichiers_enumere_les_noms_sans_vide():
    schema = schema_analyse_avec_fichiers(
        ("bulletins_salaire.pdf", "courrier_direction.pdf"),
        pages_max=2,
    )
    item = schema["properties"]["citations"]["items"]
    assert item["properties"]["fichier"]["enum"] == [
        "bulletins_salaire.pdf",
        "courrier_direction.pdf",
    ]
    assert "fichier" in item["required"]
    assert "pages" in item["required"]
    assert item["properties"]["pages"]["minItems"] == 1


def test_schema_analyse_avec_fichiers_pages_enumerees():
    """Les pages doivent etre enumerees, pas juste "integer"."""
    schema = schema_analyse_avec_fichiers(
        ("a.pdf", "b.pdf"), pages_max=3,
    )
    item = schema["properties"]["citations"]["items"]
    pages_schema = item["properties"]["pages"]["items"]
    assert pages_schema["enum"] == [1, 2, 3]


def test_schema_analyse_avec_fichiers_pages_max_defaut():
    schema = schema_analyse_avec_fichiers(("a.pdf",))
    item = schema["properties"]["citations"]["items"]
    pages_schema = item["properties"]["pages"]["items"]
    assert pages_schema["enum"] == [1]


def test_schema_analyse_avec_fichiers_sans_fichiers():
    schema = schema_analyse_avec_fichiers(())
    item = schema["properties"]["citations"]["items"]
    assert "enum" not in item["properties"]["fichier"]
    assert "fichier" not in item["required"]


def test_schema_analyse_avec_fichiers_ne_mute_pas_le_global():
    schema_analyse_avec_fichiers(("x.pdf",))
    item_global = SCHEMA_ANALYSE["properties"]["citations"]["items"]
    assert "enum" not in item_global["properties"]["fichier"]
    assert "fichier" not in item_global["required"]


def test_schema_analyse_reexporte_depuis_adaptateur():
    from beaume.adapters.generateur_ollama import (
        SCHEMA_ANALYSE as SCHEMA_ADAPTATEUR,
    )
    assert SCHEMA_ADAPTATEUR is SCHEMA_ANALYSE


# --- prompt -----------------------------------------------------------------


def test_prompt_demande_pages_et_fichier():
    prompt = construire_prompt("dossier test", [], date(2024, 1, 1))
    assert "fichier" in prompt
    assert "pages" in prompt


def test_prompt_injecte_liste_fichiers():
    prompt = construire_prompt(
        "dossier test",
        [],
        date(2024, 1, 1),
        fichiers_disponibles=(
            "bulletins_salaire.pdf",
            "courrier_direction.pdf",
        ),
    )
    assert "bulletins_salaire.pdf" in prompt
    assert "courrier_direction.pdf" in prompt


def test_prompt_sans_fichiers_disponibles():
    prompt = construire_prompt("dossier test", [], date(2024, 1, 1))
    assert "(aucun fichier)" in prompt


def test_prompt_ne_contient_plus_exemple_json():
    prompt = construire_prompt("dossier test", [], date(2024, 1, 1))
    assert "conclusions.pdf" not in prompt
    assert "EXEMPLE DE SORTIE" not in prompt


def test_prompt_demande_separation_code_numero():
    prompt = construire_prompt("dossier test", [], date(2024, 1, 1))
    assert "code" in prompt
    assert "numero" in prompt
    assert "JAMAIS le numero dans" in prompt


# --- _valider_provenance ----------------------------------------------------


def _citation(fichier: str, pages: tuple[int, ...] = ()) -> Citation:
    return Citation(
        code=CodeJuridique.CODE_CIVIL,
        numero="1240",
        date_reference=date(2024, 1, 1),
        extrait="test",
        pages=pages,
        fichier=fichier,
    )


def _analyse(*citations: Citation) -> Analyse:
    return Analyse(
        citations=list(citations),
        date_reference=date(2024, 1, 1),
    )


PAGES_PAR_FICHIER = {
    "conclusions.pdf": {1, 2, 3},
    "courrier.pdf": {1, 2},
}


def test_valider_provenance_garde_fichier_reel():
    resultat = _valider_provenance(
        _analyse(_citation("conclusions.pdf", (3,))),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    assert resultat.citations[0].fichier == "conclusions.pdf"
    assert resultat.citations[0].pages == (3,)


def test_valider_provenance_efface_fichier_inconnu():
    resultat = _valider_provenance(
        _analyse(_citation("invente.pdf", (3, 4))),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    c = resultat.citations[0]
    assert c.fichier == ""
    assert c.pages == ()


def test_valider_provenance_efface_pages_si_fichier_vide():
    resultat = _valider_provenance(
        _analyse(_citation("", (3,))),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    c = resultat.citations[0]
    assert c.fichier == ""
    assert c.pages == ()


def test_valider_provenance_filtre_pages_invalides():
    """Pages 999 et 1234 n'existent pas dans le fichier cite."""
    resultat = _valider_provenance(
        _analyse(_citation("conclusions.pdf", (1, 999, 2, 1234))),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    c = resultat.citations[0]
    assert c.fichier == "conclusions.pdf"
    assert c.pages == (1, 2)


def test_valider_provenance_vide_pages_si_aucune_valide():
    resultat = _valider_provenance(
        _analyse(_citation("conclusions.pdf", (999,))),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    c = resultat.citations[0]
    assert c.fichier == "conclusions.pdf"
    assert c.pages == ()


def test_valider_provenance_plusieurs_citations():
    resultat = _valider_provenance(
        _analyse(
            _citation("conclusions.pdf", (1,)),
            _citation("invente.pdf", (5,)),
            _citation("", ()),
        ),
        {"conclusions.pdf"},
        PAGES_PAR_FICHIER,
    )
    assert resultat.citations[0].fichier == "conclusions.pdf"
    assert resultat.citations[0].pages == (1,)
    assert resultat.citations[1].fichier == ""
    assert resultat.citations[1].pages == ()
    assert resultat.citations[2].fichier == ""
    assert resultat.citations[2].pages == ()


def test_citation_accepte_pages_defaut():
    c = Citation(
        code=CodeJuridique.CODE_CIVIL,
        numero="1240",
        date_reference=date(2024, 1, 1),
    )
    assert c.pages == ()
    assert c.fichier == ""