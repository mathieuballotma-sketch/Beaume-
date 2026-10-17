"""Benchmark comparatif des modeles Ollama pour Beaume.

Teste la conformite au schema JSON strict, la discrimination de
source, et les cas limites qui ont pose probleme avec Qwen 2.5 7B.

Usage :
    .venv/bin/python scripts/benchmark_modeles.py
    .venv/bin/python scripts/benchmark_modeles.py qwen3:4b granite3.1-dense:2b
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import ollama


SCHEMA_ANALYSE = {
    "type": "object",
    "properties": {
        "contexte": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "enum": ["code_travail", "code_civil"],
                    },
                    "numero": {"type": "string"},
                    "fichier": {
                        "type": "string",
                        "enum": [
                            "bulletins_salaire.pdf",
                            "courrier_direction.pdf",
                            "lettre_client.pdf",
                        ],
                    },
                    "pages": {
                        "type": "array",
                        "items": {"type": "integer", "enum": [1]},
                        "minItems": 1,
                    },
                },
                "required": ["code", "numero", "fichier", "pages"],
            },
        },
    },
    "required": ["contexte", "citations"],
}


@dataclass
class CasTest:
    nom: str
    prompt: str
    attendu: dict[str, Any]
    description: str = ""


CAS_TESTS = [
    CasTest(
        nom="citation_simple",
        prompt=(
            "Analyse ce dossier. Le salarie conteste son licenciement.\n\n"
            "=== LISTE DES FICHIERS ===\n"
            "- bulletins_salaire.pdf\n"
            "- courrier_direction.pdf\n\n"
            "=== DOSSIER ===\n"
            "[bulletins_salaire.pdf, page 1] Le salarie percoit 2000 euros.\n"
            "[courrier_direction.pdf, page 1] La direction confirme le "
            "licenciement.\n\n"
            "=== ARTICLES DISPONIBLES ===\n"
            "- code_travail L. 1235-3 : Si le licenciement survient pour "
            "une cause qui n'est pas reelle et serieuse...\n\n"
            "Retourne le JSON."
        ),
        attendu={
            "citations_valides": 1,
            "fichier_correct": "courrier_direction.pdf",
        },
    ),
    CasTest(
        nom="citation_avec_page",
        prompt=(
            "Analyse ce dossier.\n\n"
            "=== LISTE DES FICHIERS ===\n"
            "- bulletins_salaire.pdf\n\n"
            "=== DOSSIER ===\n"
            "[bulletins_salaire.pdf, page 1] Salaire de 2000 euros.\n\n"
            "=== ARTICLES DISPONIBLES ===\n"
            "- code_travail L. 1234-1 : Le contrat de travail...\n\n"
            "Retourne le JSON."
        ),
        attendu={"citations_valides": 1, "pages_correctes": [1]},
    ),
    CasTest(
        nom="pas_de_citation",
        prompt=(
            "Analyse ce dossier. Aucun article ne s'applique.\n\n"
            "=== LISTE DES FICHIERS ===\n"
            "- lettre_client.pdf\n\n"
            "=== DOSSIER ===\n"
            "[lettre_client.pdf, page 1] Bonjour, je vous ecris.\n\n"
            "=== ARTICLES DISPONIBLES ===\n"
            "(aucun article disponible)\n\n"
            "Retourne le JSON."
        ),
        attendu={"citations_valides": 0},
    ),
    CasTest(
        nom="code_numero_colle",
        prompt=(
            "Analyse ce dossier.\n\n"
            "=== LISTE DES FICHIERS ===\n"
            "- courrier_direction.pdf\n\n"
            "=== DOSSIER ===\n"
            "[courrier_direction.pdf, page 1] Le licenciement est conteste.\n\n"
            "=== ARTICLES DISPONIBLES ===\n"
            "- code_travail L. 1235-3 : Texte de l'article.\n\n"
            "Retourne le JSON."
        ),
        attendu={"code_separe": True},
    ),
    CasTest(
        nom="choix_parmi_deux",
        prompt=(
            "Analyse ce dossier.\n\n"
            "=== LISTE DES FICHIERS ===\n"
            "- bulletins_salaire.pdf\n"
            "- courrier_direction.pdf\n\n"
            "=== DOSSIER ===\n"
            "[bulletins_salaire.pdf, page 1] Salaire de 2000 euros.\n"
            "[courrier_direction.pdf, page 1] Licenciement confirme par "
            "la direction.\n\n"
            "=== ARTICLES DISPONIBLES ===\n"
            "- code_travail L. 1235-3 : Si le licenciement survient pour "
            "une cause qui n'est pas reelle et serieuse...\n\n"
            "Retourne le JSON."
        ),
        attendu={
            "citations_valides": 1,
            "fichier_correct": "courrier_direction.pdf",
        },
    ),
]


@dataclass
class ResultatModele:
    nom: str
    cas_reussis: int = 0
    cas_totaux: int = 0
    temps_total: float = 0.0
    erreurs: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)


def extraire_json(texte: str) -> dict | None:
    debut = texte.find("{")
    fin = texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        return json.loads(texte[debut:fin + 1])
    except json.JSONDecodeError:
        return None


def executer_test(
    modele: str, cas: CasTest, schema: dict,
) -> dict[str, Any]:
    debut = time.perf_counter()
    try:
        reponse = ollama.generate(
            model=modele,
            prompt=cas.prompt,
            format=schema,
            options={"temperature": 0.0},
        )
    except Exception as e:
        return {
            "nom": cas.nom,
            "succes": False,
            "erreur": f"Ollama : {type(e).__name__}",
            "duree_s": 0.0,
        }
    duree = time.perf_counter() - debut

    texte = reponse.get("response", "")
    brut = extraire_json(texte)

    if brut is None:
        return {
            "nom": cas.nom,
            "succes": False,
            "erreur": "JSON invalide",
            "duree_s": duree,
            "brut": texte[:200],
        }

    citations = brut.get("citations", [])
    if not isinstance(citations, list):
        return {
            "nom": cas.nom,
            "succes": False,
            "erreur": "citations n'est pas une liste",
            "duree_s": duree,
        }

    details: dict[str, Any] = {
        "nom": cas.nom,
        "succes": True,
        "duree_s": duree,
        "nb_citations": len(citations),
    }

    if cas.nom in ("citation_simple", "choix_parmi_deux"):
        if not citations:
            details["succes"] = False
            details["erreur"] = "aucune citation"
        else:
            fichier = citations[0].get("fichier", "")
            details["fichier_cite"] = fichier
            if fichier != cas.attendu["fichier_correct"]:
                details["succes"] = False
                details["erreur"] = f"fichier incorrect : {fichier}"

    elif cas.nom == "citation_avec_page":
        if not citations:
            details["succes"] = False
            details["erreur"] = "aucune citation"
        else:
            pages = citations[0].get("pages", [])
            details["pages_citees"] = pages
            if pages != cas.attendu["pages_correctes"]:
                details["succes"] = False
                details["erreur"] = f"pages incorrectes : {pages}"

    elif cas.nom == "pas_de_citation":
        if citations:
            details["succes"] = False
            details["erreur"] = f"{len(citations)} citations inventees"

    elif cas.nom == "code_numero_colle":
        for c in citations:
            code = c.get("code", "")
            if " " in code:
                details["succes"] = False
                details["erreur"] = f"code colle : {code}"
                break

    return details


def benchmark(modele: str) -> ResultatModele:
    resultat = ResultatModele(nom=modele)
    print(f"\n{'=' * 65}")
    print(f"  Modele : {modele}")
    print(f"{'=' * 65}")

    for cas in CAS_TESTS:
        resultat.cas_totaux += 1
        detail = executer_test(modele, cas, SCHEMA_ANALYSE)
        resultat.details.append(detail)
        resultat.temps_total += detail.get("duree_s", 0.0)

        if detail.get("succes"):
            resultat.cas_reussis += 1
            print(f"  OK   {cas.nom:22s} ({detail['duree_s']:.1f}s)")
        else:
            msg = detail.get("erreur", "inconnue")
            resultat.erreurs.append(f"{cas.nom} : {msg}")
            print(f"  FAIL {cas.nom:22s} : {msg}")

    print(
        f"\n  Resultat : {resultat.cas_reussis}/{resultat.cas_totaux} "
        f"en {resultat.temps_total:.1f}s"
    )
    return resultat


def main() -> None:
    modeles = sys.argv[1:] if len(sys.argv) > 1 else [
        "qwen3:4b",
        "granite3.1-dense:2b",
        "qwen2.5:7b-instruct",
    ]

    resultats = []
    for modele in modeles:
        resultats.append(benchmark(modele))

    print(f"\n{'=' * 65}")
    print("  COMPARAISON FINALE")
    print(f"{'=' * 65}")
    print(f"  {'Modele':24s} {'Reussis':>8s} {'Temps':>8s}")
    print(f"  {'-' * 24} {'-' * 8} {'-' * 8}")
    for r in resultats:
        print(
            f"  {r.nom:24s} {r.cas_reussis}/{r.cas_totaux:<6d} "
            f"{r.temps_total:>7.1f}s"
        )

    meilleur = max(resultats, key=lambda r: r.cas_reussis)
    print(f"\n  Meilleur : {meilleur.nom} "
          f"({meilleur.cas_reussis}/{meilleur.cas_totaux})")


if __name__ == "__main__":
    main()
