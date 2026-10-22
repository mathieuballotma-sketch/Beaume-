"""Tests de la fusion references directes / FTS5 dans analyser().

Couvre la logique ajoutee au fichier corrige :
  - les references directes passent avant les articles FTS5 ;
  - un article present dans les deux voies n'apparait qu'une fois ;
  - le plafond limite_candidats s'applique apres fusion ;
  - les mentions non resolues produisent un avertissement visible ;
  - la detection directe tourne sur tous les chunks, pas seulement
    ceux qui passent le selecteur pour le prompt ;
  - aucun candidat produit un avertissement explicite ;
  - un depot sans resoudre_article degrade proprement (pas d'exception) ;
  - FTS5 seul continue de fonctionner normalement.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from beaume.application import analyse_dossier as mod
from beaume.application.analyse_dossier import AnalyseDossier
from beaume.legal.model import CodeJuridique
from beaume.ports.resolveur_articles import ResolutionArticle, StatutResolution


DATE_REF = date(2020, 1, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _article(article_id):
    """Article factice : id + version_a non None (requis par _enrichir_articles)."""
    a = MagicMock()
    a.id.valeur = article_id
    a.version_a.return_value = MagicMock()
    return a


def _resolution_unique(article_id, code, numero):
    return ResolutionArticle(
        statut=StatutResolution.UNIQUE,
        article_id_famille=article_id,
        code=code,
        numero_normalise=numero,
    )


class _FauxDepot:
    def __init__(self, articles=None, resolutions=None):
        self.articles = articles or {}
        self.resolutions = resolutions or {}
        self.resoudre_appels = []

    def resoudre_article(self, code, numero, date_reference, *, strict=True):
        self.resoudre_appels.append((code, numero, date_reference, strict))
        return self.resolutions.get(
            (code, numero),
            ResolutionArticle(statut=StatutResolution.REFERENCE_ABSENTE),
        )

    def trouver_par_id(self, article_id, date_reference):
        return self.articles.get(article_id)


class _DepotSansResolution:
    """Depot sans resoudre_article : verifie la degradation propre."""

    def __init__(self, articles=None):
        self.articles = articles or {}

    def trouver_par_id(self, article_id, date_reference):
        return self.articles.get(article_id)


class _ChercheurParTexte:
    """Retourne un jeu d'IDs en fonction du texte du chunk.

    Comparaison insensible a la casse : evite de dependre de la casse
    exacte du texte dans les tests.
    """

    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.appels = []

    def chercher(self, texte, limite=10):
        self.appels.append((texte, limite))
        texte_bas = texte.lower()
        for cle, ids in self.mapping.items():
            if cle.lower() in texte_bas:
                return [SimpleNamespace(article_id=i) for i in ids]
        return []


class _GenerateurCapture:
    def __init__(self, reponse=None):
        self.reponse = reponse or {"citations": []}
        self.prompts = []

    def generer(self, prompt, temperature=0.0, format=None):
        self.prompts.append(
            {"prompt": prompt, "format": format, "temperature": temperature}
        )
        return SimpleNamespace(
            modele="faux",
            tokens_reponse=1,
            duree_s=0.01,
            texte=json.dumps(self.reponse),
        )


class _SelecteurSimple:
    def __init__(self, prompt_texte="PROMPT"):
        self.prompt_texte = prompt_texte

    def selectionner(self, chunks):
        return chunks

    def formater_pour_prompt(self, selection):
        return self.prompt_texte


def _fichier_ok(nom, textes):
    return SimpleNamespace(
        ok=True,
        chemin=Path(nom),
        chunks=[
            SimpleNamespace(texte=t, page_debut=i + 1, page_fin=i + 1)
            for i, t in enumerate(textes)
        ],
    )


def _instancier(depot, chercheur, generateur, selecteur, fichiers):
    obj = AnalyseDossier.__new__(AnalyseDossier)
    obj.depot = depot
    obj.chercheur = chercheur
    obj.generateur = generateur
    obj.selecteur = selecteur
    obj.lecteur = SimpleNamespace(
        lire=lambda d: SimpleNamespace(fichiers=fichiers)
    )
    obj.limite_candidats = 10
    obj.limite_articles = 10
    return obj


@pytest.fixture
def patch_prompt(monkeypatch):
    """Intercepte construire_prompt et le schema pour ne pas dependre
    de leur implementation. Capture la liste d'articles transmise."""
    captures = {}

    def _faux_construire_prompt(texte, articles, date_ref, **kw):
        captures["articles"] = list(articles)
        return "PROMPT FICTIF"

    def _faux_schema(**kw):
        return {"type": "object"}

    monkeypatch.setattr(mod, "construire_prompt", _faux_construire_prompt)
    monkeypatch.setattr(mod, "schema_analyse_avec_candidats", _faux_schema)
    return captures


# ---------------------------------------------------------------------------
# Fusion directs / FTS5
# ---------------------------------------------------------------------------

def test_directs_passent_avant_fts5(patch_prompt):
    art_direct = _article("LEGIARTI_DIRECT")
    art_fts5 = _article("LEGIARTI_FTS5")
    res = _resolution_unique(
        "LEGIARTI_DIRECT", CodeJuridique.CODE_CONSOMMATION, "L137-2"
    )
    depot = _FauxDepot(
        articles={
            "LEGIARTI_DIRECT": art_direct,
            "LEGIARTI_FTS5": art_fts5,
        },
        resolutions={(CodeJuridique.CODE_CONSOMMATION, "L137-2"): res},
    )
    chercheur = _ChercheurParTexte({"L.137-2": ["LEGIARTI_FTS5"]})
    generateur = _GenerateurCapture()
    selecteur = _SelecteurSimple()
    fichiers = [
        _fichier_ok("doc.pdf", ["Vu L.137-2 du Code de la consommation."])
    ]
    obj = _instancier(depot, chercheur, generateur, selecteur, fichiers)

    obj.analyser(Path("/tmp/dossier"), DATE_REF)

    ids = [a.id.valeur for a in patch_prompt["articles"]]
    assert ids == ["LEGIARTI_DIRECT", "LEGIARTI_FTS5"]


def test_dedup_direct_et_fts5(patch_prompt):
    """Un article present dans les deux voies n'apparait qu'une fois."""
    art = _article("LEGIARTI_X")
    res = _resolution_unique(
        "LEGIARTI_X", CodeJuridique.CODE_CONSOMMATION, "L137-2"
    )
    depot = _FauxDepot(
        articles={"LEGIARTI_X": art},
        resolutions={(CodeJuridique.CODE_CONSOMMATION, "L137-2"): res},
    )
    chercheur = _ChercheurParTexte({"L.137-2": ["LEGIARTI_X"]})
    generateur = _GenerateurCapture()
    selecteur = _SelecteurSimple()
    fichiers = [
        _fichier_ok("doc.pdf", ["L.137-2 du Code de la consommation."])
    ]
    obj = _instancier(depot, chercheur, generateur, selecteur, fichiers)

    obj.analyser(Path("/tmp/dossier"), DATE_REF)

    ids = [a.id.valeur for a in patch_prompt["articles"]]
    assert ids == ["LEGIARTI_X"]


def test_plafond_applique_apres_fusion(patch_prompt):
    """limite_candidats s'applique a la liste fusionnee : directs d'abord."""
    ids_directs = ["LEGIARTI_D1", "LEGIARTI_D2", "LEGIARTI_D3"]
    ids_fts5 = ["LEGIARTI_F1", "LEGIARTI_F2"]
    arts = {i: _article(i) for i in ids_directs + ids_fts5}
    resolutions = {
        (CodeJuridique.CODE_CONSOMMATION, "L137-2"): _resolution_unique(
            "LEGIARTI_D1", CodeJuridique.CODE_CONSOMMATION, "L137-2"
        ),
        (CodeJuridique.CODE_CIVIL, "2224"): _resolution_unique(
            "LEGIARTI_D2", CodeJuridique.CODE_CIVIL, "2224"
        ),
        (CodeJuridique.CODE_TRAVAIL, "L1233-3"): _resolution_unique(
            "LEGIARTI_D3", CodeJuridique.CODE_TRAVAIL, "L1233-3"
        ),
    }
    depot = _FauxDepot(articles=arts, resolutions=resolutions)
    chercheur = _ChercheurParTexte({"L.137-2": ids_fts5})
    generateur = _GenerateurCapture()
    selecteur = _SelecteurSimple()
    fichiers = [
        _fichier_ok(
            "doc.pdf",
            [
                "L.137-2 du Code de la consommation.",
                "2224 du Code civil.",
                "L1233-3 du Code du travail.",
            ],
        )
    ]
    obj = _instancier(depot, chercheur, generateur, selecteur, fichiers)
    obj.limite_candidats = 2

    obj.analyser(Path("/tmp/dossier"), DATE_REF)

    ids = [a.id.valeur for a in patch_prompt["articles"]]
    assert ids == ["LEGIARTI_D1", "LEGIARTI_D2"]


def test_mention_non_resolue_avertit(patch_prompt):
    """Une reference detectee mais non resolue reste visible."""
    res_prov = ResolutionArticle(
        statut=StatutResolution.PROVENANCE_INSUFFISANTE,
        article_id_famille="LEGIARTI_X",
        code=CodeJuridique.CODE_CONSOMMATION,
        numero_normalise="L137-2",
        message="provenance insuffisante",
    )
    depot = _FauxDepot(
        articles={"LEGIARTI_X": _article("LEGIARTI_X")},
        resolutions={(CodeJuridique.CODE_CONSOMMATION, "L137-2"): res_prov},
    )
    chercheur = _ChercheurParTexte()
    generateur = _GenerateurCapture()
    selecteur = _SelecteurSimple()
    fichiers = [
        _fichier_ok("doc.pdf", ["Vu L.137-2 du Code de la consommation."])
    ]
    obj = _instancier(depot, chercheur, generateur, selecteur, fichiers)

    analyse = obj.analyser(Path("/tmp/dossier"), DATE_REF)

    messages = " ".join(analyse.avertissements)
    assert "non resolue" in messages or "non résolue" in messages
    assert "L.137-2" in messages


# ---------------------------------------------------------------------------
# Perimetre de la detection directe
# ---------------------------------------------------------------------------

def test_detection_sur_tous_les_chunks_pas_seulement_selection(patch_prompt):
    """Trois chunks avec trois references ; le selecteur n'en garde qu'un
    pour le prompt. Les trois references doivent quand meme etre detectees."""
    arts = {f"LEGIARTI_{i}": _article(f"LEGIARTI_{i}") for i in range(1, 4)}
    resolutions = {
        (CodeJuridique.CODE_CONSOMMATION, "L137-2"): _resolution_unique(
            "LEGIARTI_1", CodeJuridique.CODE_CONSOMMATION, "L137-2"
        ),
        (CodeJuridique.CODE_CIVIL, "2224"): _resolution_unique(
            "LEGIARTI_2", CodeJuridique.CODE_CIVIL, "2224"
        ),
        (CodeJuridique.CODE_TRAVAIL, "L1233-3"): _resolution_unique(
            "LEGIARTI_3", CodeJuridique.CODE_TRAVAIL, "L1233-3"
        ),
    }
    depot = _FauxDepot(articles=arts, resolutions=resolutions)

    class _SelecteurPremierSeul(_SelecteurSimple):
        def selectionner(self, chunks):
            return chunks[:1]

    selecteur = _SelecteurPremierSeul()
    chercheur = _ChercheurParTexte()
    generateur = _GenerateurCapture()
    fichiers = [
        _fichier_ok(
            "doc.pdf",
            [
                "L.137-2 du Code de la consommation.",
                "2224 du Code civil.",
                "L1233-3 du Code du travail.",
            ],
        )
    ]
    obj = _instancier(depot, chercheur, generateur, selecteur, fichiers)

    obj.analyser(Path("/tmp/dossier"), DATE_REF)

    ids = {a.id.valeur for a in patch_prompt["articles"]}
    assert ids == {"LEGIARTI_1", "LEGIARTI_2", "LEGIARTI_3"}


# ---------------------------------------------------------------------------
# Cas limites
# ---------------------------------------------------------------------------

def test_aucun_candidat_avertit(patch_prompt):
    depot = _FauxDepot()
    chercheur = _ChercheurParTexte()
    generateur = _GenerateurCapture()
    selecteur = _SelecteurSimple()
    fichiers = [
        _fichier_ok("doc.pdf", ["Un texte sans aucune reference."])
    ]
    obj = _instancier(depot, chercheur, generateur, selecteur, fichiers)

    analyse = obj.analyser(Path("/tmp/dossier"), DATE_REF)

    messages = " ".join(analyse.avertissements)
    assert "Aucun article candidat" in messages


def test_depot_sans_resoudre_ne_casse_pas(patch_prompt):
    """Un depot sans resoudre_article ne doit pas lever : la detection
    directe est simplement vide, FTS5 continue."""
    art_fts5 = _article("LEGIARTI_FTS5")
    depot = _DepotSansResolution(articles={"LEGIARTI_FTS5": art_fts5})
    chercheur = _ChercheurParTexte({"L.137-2": ["LEGIARTI_FTS5"]})
    generateur = _GenerateurCapture()
    selecteur = _SelecteurSimple()
    fichiers = [
        _fichier_ok("doc.pdf", ["Vu L.137-2 du Code de la consommation."])
    ]
    obj = _instancier(depot, chercheur, generateur, selecteur, fichiers)

    obj.analyser(Path("/tmp/dossier"), DATE_REF)

    ids = [a.id.valeur for a in patch_prompt["articles"]]
    assert "LEGIARTI_FTS5" in ids


def test_fts5_seul_fonctionne(patch_prompt):
    """Non-regression : sans reference directe, FTS5 seul est transmis."""
    art = _article("LEGIARTI_FTS5")
    depot = _FauxDepot(articles={"LEGIARTI_FTS5": art})
    chercheur = _ChercheurParTexte({"un fait quelconque": ["LEGIARTI_FTS5"]})
    generateur = _GenerateurCapture()
    selecteur = _SelecteurSimple()
    fichiers = [
        _fichier_ok("doc.pdf", ["Un fait quelconque sans reference."])
    ]
    obj = _instancier(depot, chercheur, generateur, selecteur, fichiers)

    obj.analyser(Path("/tmp/dossier"), DATE_REF)

    ids = [a.id.valeur for a in patch_prompt["articles"]]
    assert ids == ["LEGIARTI_FTS5"]