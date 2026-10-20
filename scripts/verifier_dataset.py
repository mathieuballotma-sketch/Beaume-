"""Audite la structure de `train_llm_v2.jsonl` et son manifeste.

Les controles deterministes verifient que les citations selectionnent un
article_id effectivement fourni au modele et respectent le contrat de sortie
de Beaume. Ils ne valident pas la pertinence juridique d'un exemple. L'option
`--juge-llm` ajoute uniquement un avis de triage, jamais une preuve.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from beaume.config import paths


FICHIER_DEFAUT = Path("data/entrainement/train_llm_v2.jsonl")
MANIFESTE_DEFAUT = Path("data/entrainement/train_manifest_v2.json")
CHAMPS_CIBLE_REQUIS = {"contexte", "citations"}
CHAMPS_CIBLE_OPTIONNELS = {"parties", "demandes", "problemes_juridiques"}
CHAMPS_CITATION = {"article_id", "fichier", "pages"}
MARQUEUR_CANDIDATS = "=== ARTICLES CANDIDATS ==="


def _compact(texte: str) -> str:
    return re.sub(r"\s+", " ", texte).strip()


def _messages(
    ligne: Any,
    numero_ligne: int,
) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(ligne, dict):
        raise ValueError(f"Ligne {numero_ligne}: la racine JSON doit etre un objet")
    conversations = ligne.get("conversations")
    if not isinstance(conversations, list):
        raise ValueError(f"Ligne {numero_ligne}: champ conversations invalide")
    par_role: dict[str, list[str]] = {}
    for message in conversations:
        if not isinstance(message, dict):
            raise ValueError(f"Ligne {numero_ligne}: message invalide")
        role = message.get("from")
        value = message.get("value")
        if role not in {"system", "human", "gpt"} or not isinstance(value, str):
            raise ValueError(f"Ligne {numero_ligne}: role ou valeur de message invalide")
        par_role.setdefault(role, []).append(value)
    if len(par_role.get("human", [])) != 1 or len(par_role.get("gpt", [])) != 1:
        raise ValueError(f"Ligne {numero_ligne}: un message human et gpt sont requis")
    humain = par_role["human"][0]
    assistant = par_role["gpt"][0]
    reponse = json.loads(assistant)
    if not isinstance(reponse, dict):
        raise ValueError(f"Ligne {numero_ligne}: la reponse cible doit etre un objet JSON")
    return humain, assistant, reponse


def _extraire_fait_et_candidats(
    prompt: str,
) -> tuple[str, dict[str, dict[str, str]]]:
    fait_match = re.search(
        r"\[dossier\.pdf,\s*page\s*1\]\s*(.*?)\s*\n\s*=== ARTICLES CANDIDATS ===",
        prompt,
        flags=re.DOTALL,
    )
    if not fait_match:
        raise ValueError("marqueur de fait `[dossier.pdf, page 1]` absent")
    fait = _compact(fait_match.group(1))

    bloc_match = re.search(
        r"=== ARTICLES CANDIDATS ===\s*\n(.*?)(?:\n\s*=== DATE DE REFERENCE ===|\Z)",
        prompt,
        flags=re.DOTALL,
    )
    if not bloc_match:
        raise ValueError("bloc ARTICLES CANDIDATS absent")

    candidats: dict[str, dict[str, str]] = {}
    courant: dict[str, str] | None = None
    entete = re.compile(
        r"^\s*-\s+article_id=(\S+)\s+code=(\S+)\s+numero=(.+?)\s*$"
    )
    for ligne in bloc_match.group(1).splitlines():
        match = entete.match(ligne)
        if match:
            article_id, code, numero = match.groups()
            if article_id in candidats:
                raise ValueError(f"article_id candidat duplique: {article_id}")
            courant = {
                "article_id": article_id,
                "code": code,
                "numero": numero.strip(),
                "texte": "",
            }
            candidats[article_id] = courant
            continue
        if courant is None or not ligne.strip():
            continue
        contenu = re.match(r"\s*texte officiel\s*:\s*(.*)$", ligne)
        morceau = contenu.group(1) if contenu else ligne.strip()
        courant["texte"] = _compact(f"{courant['texte']} {morceau}")

    if not candidats and "(aucun article candidat)" not in bloc_match.group(1):
        raise ValueError("aucun candidat parse et aucun marqueur de liste vide")
    return fait, candidats


def verifier_ligne(
    ligne: Any,
    numero_ligne: int,
    meta: Any = None,
    sha256_ligne: str | None = None,
) -> dict[str, Any]:
    """Controle les invariants deterministes, sans juger la pertinence."""
    erreurs: list[str] = []
    avertissements: list[str] = []
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
        avertissements.append("metadonnees du manifeste invalides")
    empreinte_attendue = meta.get("sha256_ligne")
    if empreinte_attendue is not None:
        if not isinstance(empreinte_attendue, str):
            avertissements.append("empreinte de ligne invalide dans le manifeste")
        elif sha256_ligne is None:
            avertissements.append("empreinte de ligne non verifiee")
        elif empreinte_attendue != sha256_ligne:
            erreurs.append("le contenu de la ligne ne correspond pas au manifeste")

    try:
        humain, _, reponse = _messages(ligne, numero_ligne)
        fait, candidats = _extraire_fait_et_candidats(humain)
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "ligne": numero_ligne,
            "id": meta.get("id"),
            "erreurs_structure": [*erreurs, str(exc)],
            "avertissements": avertissements,
            "n_candidats": 0,
            "n_citations": 0,
            "controle_pertinence_juridique": "non_effectue",
        }

    champs_inconnus = set(reponse) - CHAMPS_CIBLE_REQUIS - CHAMPS_CIBLE_OPTIONNELS
    champs_manquants = CHAMPS_CIBLE_REQUIS - set(reponse)
    if champs_inconnus:
        erreurs.append("champs de reponse hors schema: " + ", ".join(sorted(champs_inconnus)))
    if champs_manquants:
        erreurs.append("champs requis absents: " + ", ".join(sorted(champs_manquants)))
    if not isinstance(reponse.get("contexte"), str):
        erreurs.append("contexte doit etre une chaine")
    for champ in CHAMPS_CIBLE_OPTIONNELS:
        if champ in reponse and (
            not isinstance(reponse[champ], list)
            or any(not isinstance(element, str) for element in reponse[champ])
        ):
            erreurs.append(f"{champ} doit etre une liste de chaines")

    citations = reponse.get("citations")
    if not isinstance(citations, list):
        erreurs.append("citations doit etre une liste")
        citations = []

    ids_cites: list[str] = []
    for index, citation in enumerate(citations, start=1):
        if not isinstance(citation, dict):
            erreurs.append(f"citation {index}: objet attendu")
            continue
        champs_citation = set(citation)
        if champs_citation != CHAMPS_CITATION:
            erreurs.append(
                f"citation {index}: champs attendus exactement: "
                + ", ".join(sorted(CHAMPS_CITATION))
            )
        article_id = citation.get("article_id")
        if not isinstance(article_id, str) or not article_id:
            erreurs.append(f"citation {index}: article_id doit etre une chaine non vide")
            continue
        ids_cites.append(article_id)
        candidat = candidats.get(article_id)
        if candidat is None:
            erreurs.append(f"citation {index}: article_id absent des candidats")

        if citation.get("fichier") != "dossier.pdf":
            erreurs.append(f"citation {index}: fichier inattendu")
        pages = citation.get("pages")
        if (
            not isinstance(pages, list)
            or not pages
            or any(not isinstance(page, int) or isinstance(page, bool) or page <= 0 for page in pages)
        ):
            erreurs.append(f"citation {index}: pages doit etre une liste d'entiers positifs")
        elif pages != [1]:
            erreurs.append(f"citation {index}: pages incoherentes avec le PDF synthetique")

    if len(ids_cites) != len(set(ids_cites)):
        erreurs.append("la reponse cite plusieurs fois le meme article_id")

    type_exemple = meta.get("type")
    target_id = meta.get("article_id_cible")
    manifest_ids = meta.get("article_ids_candidats")
    ids_prompt = list(candidats)
    if manifest_ids is not None:
        if not isinstance(manifest_ids, list) or manifest_ids != ids_prompt:
            erreurs.append("les article_ids du manifeste ne correspondent pas au prompt")
    nombre_candidats = meta.get("n_candidats")
    if nombre_candidats is not None and (
        not isinstance(nombre_candidats, int)
        or isinstance(nombre_candidats, bool)
        or nombre_candidats != len(candidats)
    ):
        erreurs.append("n_candidats du manifeste ne correspond pas au prompt")

    if type_exemple == "positif_synthetique_non_verifie":
        if len(ids_cites) != 1:
            erreurs.append("exemple positif attendu avec exactement une citation")
        if not isinstance(target_id, str) or not target_id:
            erreurs.append("article_id_cible absent du manifeste")
        elif target_id not in candidats:
            erreurs.append("cible positive absente des candidats")
        elif ids_cites != [target_id]:
            erreurs.append("la citation cible ne correspond pas a l'article_id du manifeste")
    elif type_exemple == "hors_domaine_sans_reference_juridique":
        if citations:
            erreurs.append("exemple hors domaine attendu avec citations vides")
    elif type_exemple == "juridique_sans_candidat_non_verifie":
        if citations:
            erreurs.append("exemple sans candidat attendu avec citations vides")
        identifiant_masque = meta.get("article_id_source_masque")
        if not isinstance(identifiant_masque, str) or not identifiant_masque:
            erreurs.append("article_id_source_masque absent du manifeste")
        elif identifiant_masque in candidats:
            erreurs.append("la cible masquee apparait dans la liste de candidats")
        avertissements.append(
            "negatif juridique synthetique non valide : ne pas l'utiliser pour entrainer "
            "avant verification des candidats et du label"
        )
    elif type_exemple is None:
        avertissements.append("type d'exemple absent du manifeste")
    else:
        erreurs.append(f"type d'exemple inconnu dans le manifeste: {type_exemple}")

    statut = meta.get("statut", "non_documente")
    if statut != "genere_auto_a_revoir":
        avertissements.append(
            f"statut {statut!r} ne prouve pas une validation humaine; conserver la provenance"
        )
    avertissements.append("pertinence juridique non validee par un juriste")

    return {
        "ligne": numero_ligne,
        "id": meta.get("id"),
        "type": type_exemple,
        "statut_donnees": statut,
        "n_candidats": len(candidats),
        "n_citations": len(citations),
        "erreurs_structure": erreurs,
        "avertissements": avertissements,
        "controle_pertinence_juridique": "non_effectue",
        "longueur_fait": len(fait),
    }


def _charger_manifeste(
    path: Path | None,
    section: str = "exemples_llm",
) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    with path.open(encoding="utf-8") as fichier:
        data = json.load(fichier)
    if not isinstance(data, dict):
        raise ValueError("la racine du manifeste doit etre un objet JSON")
    exemples = data.get(section, [])
    if not isinstance(exemples, list) or any(not isinstance(x, dict) for x in exemples):
        raise ValueError(f"{section} doit etre une liste d'objets")
    return exemples


def _juger_llm(fait: str, article: str, modele: str) -> dict[str, Any]:
    """Avis automatique de triage, jamais une preuve de pertinence."""
    import ollama

    prompt = f"""Tu aides a trier des exemples synthetiques pour une recherche juridique.
Ne valide pas l'article parce qu'il partage des mots avec le fait. Si les
conditions d'application ne sont pas etablies par les seuls textes fournis,
reponds 'incertain'.

TEXTE CANDIDAT : {article[:1200]}
FAIT : {fait}

Reponds en JSON strict avec `avis` parmi `pertinent`, `non_pertinent`,
`incertain`, et une raison courte."""
    reponse = ollama.generate(
        model=modele,
        prompt=prompt,
        format={
            "type": "object",
            "properties": {
                "avis": {"type": "string", "enum": ["pertinent", "non_pertinent", "incertain"]},
                "raison": {"type": "string"},
            },
            "required": ["avis", "raison"],
        },
        options={"temperature": 0.0},
    )
    data = json.loads(reponse["response"])
    if not isinstance(data, dict) or data.get("avis") not in {
        "pertinent", "non_pertinent", "incertain"
    } or not isinstance(data.get("raison"), str):
        raise ValueError("reponse du juge LLM hors schema")
    return {"avis": data["avis"], "raison": data["raison"], "modele": modele}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fichier", type=Path, default=FICHIER_DEFAUT)
    parser.add_argument("--manifeste", type=Path, default=MANIFESTE_DEFAUT)
    parser.add_argument(
        "--section-manifeste",
        choices=("exemples_llm", "exemples_llm_sans_candidat_a_revoir"),
        default="exemples_llm",
        help="Section de metadonnees associee au JSONL audite.",
    )
    parser.add_argument("--sortie", type=Path, default=paths.TMP / "audit_dataset_v2.json")
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--juge-llm", action="store_true")
    parser.add_argument("--modele-juge", default="qwen2.5:7b-instruct")
    args = parser.parse_args()
    if not args.fichier.is_file():
        parser.error(f"Dataset introuvable : {args.fichier}")
    if args.limite is not None and args.limite <= 0:
        parser.error("--limite doit etre positif")
    try:
        metadata = _charger_manifeste(args.manifeste, args.section_manifeste)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(f"Manifeste invalide: {type(exc).__name__}")

    resultats: list[dict[str, Any]] = []
    with args.fichier.open(encoding="utf-8") as fichier:
        for numero_ligne, brut in enumerate(fichier, start=1):
            if args.limite is not None and len(resultats) >= args.limite:
                break
            try:
                ligne = json.loads(brut)
                meta = metadata[numero_ligne - 1] if numero_ligne <= len(metadata) else {}
                sha256_ligne = hashlib.sha256(
                    brut.rstrip("\r\n").encode("utf-8")
                ).hexdigest()
                resultat = verifier_ligne(
                    ligne, numero_ligne, meta, sha256_ligne=sha256_ligne,
                )
                if args.juge_llm and not resultat["erreurs_structure"]:
                    humain, _, reponse = _messages(ligne, numero_ligne)
                    fait, candidats = _extraire_fait_et_candidats(humain)
                    avis = []
                    for citation in reponse.get("citations", []):
                        candidat = candidats.get(citation.get("article_id"))
                        if candidat and candidat["texte"]:
                            avis.append(_juger_llm(fait, candidat["texte"], args.modele_juge))
                    resultat["avis_llm_triage"] = avis
                resultats.append(resultat)
            except Exception as exc:
                resultats.append({
                    "ligne": numero_ligne,
                    "erreurs_structure": [type(exc).__name__],
                    "avertissements": [],
                    "controle_pertinence_juridique": "non_effectue",
                })

    n = len(resultats)
    n_erreurs = sum(bool(r.get("erreurs_structure")) for r in resultats)
    n_avertissements = sum(len(r.get("avertissements", [])) for r in resultats)
    avertissements_globaux = []
    if not args.manifeste.is_file():
        avertissements_globaux.append(
            "manifeste absent : provenance, seed, date, modele et cibles non relies aux lignes"
        )
    elif len(metadata) != n and args.limite is None:
        avertissements_globaux.append(
            f"nombre de lignes ({n}) different des entrees du manifeste ({len(metadata)})"
        )
    rapport = {
        "fichier": str(args.fichier),
        "manifeste": str(args.manifeste) if args.manifeste.is_file() else None,
        "section_manifeste": args.section_manifeste,
        "n_lignes": n,
        "n_lignes_avec_erreurs_structure": n_erreurs,
        "n_avertissements": n_avertissements,
        "avertissements_globaux": avertissements_globaux,
        "n_entrees_manifeste": len(metadata),
        "avis_juriste": "absent; un avis LLM eventuel reste un triage non probant",
        "resultats": resultats,
    }
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    temporaire = args.sortie.with_name(args.sortie.name + ".tmp")
    temporaire.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    temporaire.replace(args.sortie)
    print(f"Lignes auditees : {n}")
    print(f"Erreurs structure: {n_erreurs}")
    print(f"Avertissements   : {n_avertissements}")
    if avertissements_globaux:
        print("Manifeste        : incoherent ou absent (voir rapport)")
    print("Pertinence legale: non validee par ce script")
    print(f"Rapport          : {args.sortie}")
    return 1 if n_erreurs else 0


if __name__ == "__main__":
    raise SystemExit(main())
