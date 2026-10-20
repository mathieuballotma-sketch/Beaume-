"""Modele et rendu Markdown d'un rapport d'analyse."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from beaume.legal.analyse import Analyse
from beaume.legal.model import ResultatVerification


@dataclass(frozen=True)
class Rapport:
    dossier: Path
    date_reference: date
    analyse: Analyse
    verifications: list[ResultatVerification]
    modele_llm: str
    duree_s: float

    @property
    def citations_valides(self) -> list[ResultatVerification]:
        return [v for v in self.verifications if v.est_valide]

    @property
    def citations_rejetees(self) -> list[ResultatVerification]:
        return [v for v in self.verifications if not v.est_valide]


def _lien_legifrance(article_id: str) -> str:
    return f"https://www.legifrance.gouv.fr/codes/article_lc/{article_id}"


def _tronquer(texte: str, longueur: int = 300) -> str:
    t = texte.strip()
    if len(t) <= longueur:
        return t
    return t[:longueur].rstrip() + "..."


def _formater_source_dossier(c) -> str | None:
    """Retourne une ligne 'Source dans le dossier' si disponible."""
    if not c.fichier:
        return None
    pages_str = ", ".join(str(p) for p in c.pages) if c.pages else "?"
    return (
        f"- **Source dans le dossier** : `{c.fichier}` "
        f"(page(s) {pages_str})"
    )


def _formater_verification(v: ResultatVerification) -> str:
    c = v.citation
    lignes = [
        f"### {c.code.value} - Article {c.numero}",
        "",
        f"- **Date de reference** : {c.date_reference.isoformat()}",
    ]
    source = _formater_source_dossier(c)
    if source:
        lignes.append(source)
    if v.version:
        lignes.append(
            f"- **Identifiant Legifrance** : `{v.version.article_id.valeur}`"
        )
        lignes.append(
            f"- **Lien** : {_lien_legifrance(v.version.article_id.valeur)}"
        )
    if c.extrait:
        lignes.append(f"- **Extrait cite** : *{c.extrait}*")
    if v.version:
        lignes.append("")
        lignes.append(f"> {v.version.texte}")
    lignes.append("")
    return "\n".join(lignes)


def _formater_rejet(v: ResultatVerification) -> str:
    """Formate une citation rejetee avec sa provenance."""
    c = v.citation
    lignes = [
        f"### {c.code.value} - Article {c.numero} (au {c.date_reference.isoformat()})",
        "",
        f"- **Verdict** : `{v.statut.value}`",
        f"- **Raison** : {v.message}",
    ]
    source = _formater_source_dossier(c)
    if source:
        lignes.append(source)
    if c.extrait:
        lignes.append(
            f"- **Extrait issu du corpus local** : *{_tronquer(c.extrait)}*"
        )
    if v.version:
        lignes.append(
            f"- **Texte officiel (extrait)** : *{_tronquer(v.version.texte)}*"
        )
    lignes.append("")
    return "\n".join(lignes)


def _ligne_etat(analyse: Analyse) -> list[str]:
    """Genere la ligne d'etat du rapport (COMPLET / PARTIEL / ECHEC)."""
    etat = analyse.etat
    if etat == "COMPLET":
        return ["- **Etat** : COMPLET", ""]
    if etat == "PARTIEL":
        lignes = ["- **Etat** : PARTIEL"]
        if analyse.fichiers_ignores:
            lignes.append(
                f"- **Fichiers ignores** : {len(analyse.fichiers_ignores)}"
            )
            for nom in analyse.fichiers_ignores:
                lignes.append(f"  - `{nom}`")
        if analyse.avertissements:
            lignes.append("- **Avertissements** :")
            lignes.extend(f"  - {message}" for message in analyse.avertissements)
        lignes.append("")
        return lignes
    lignes = ["- **Etat** : ECHEC"]
    if analyse.erreur:
        lignes.append(f"- **Raison** : {analyse.erreur}")
    lignes.append("")
    return lignes


def rendre_markdown(rapport: Rapport) -> str:
    a = rapport.analyse
    lignes = [
        "# Rapport d'analyse - Beaume",
        "",
        f"- **Dossier** : `{rapport.dossier.name}`",
        f"- **Date de reference** : {rapport.date_reference.isoformat()}",
        f"- **Modele LLM** : {rapport.modele_llm}",
        f"- **Duree d'analyse** : {rapport.duree_s:.2f} s",
        f"- **Citations valides** : {len(rapport.citations_valides)}",
        f"- **Citations rejetees** : {len(rapport.citations_rejetees)}",
    ]
    lignes += _ligne_etat(a)
    lignes += [
        "---",
        "",
        "## Contexte",
        "",
        a.contexte or "_(non renseigne)_",
        "",
    ]

    if a.parties:
        lignes += ["## Parties", ""] + [f"- {p}" for p in a.parties] + [""]
    if a.demandes:
        lignes += ["## Demandes", ""] + [f"- {d}" for d in a.demandes] + [""]
    if a.problemes_juridiques:
        lignes += ["## Problemes juridiques identifies", ""]
        lignes += [f"- {p}" for p in a.problemes_juridiques]
        lignes += [""]

    lignes += ["## Articles applicables (verifies)", ""]
    if rapport.citations_valides:
        for v in rapport.citations_valides:
            lignes.append(_formater_verification(v))
    else:
        lignes.append("_(aucune citation verifiee)_")
        lignes.append("")

    if rapport.citations_rejetees:
        lignes += [
            "---",
            "",
            "## Annexes - citations rejetees par le verificateur",
            "",
            "Ces citations ont ete produites par le modele mais n'ont pas "
            "ete confirmees dans le corpus. Elles ne doivent pas etre "
            "utilisees en l'etat.",
            "",
        ]
        for v in rapport.citations_rejetees:
            lignes.append(_formater_rejet(v))
        lignes.append("")

    lignes += [
        "---",
        "",
        "> **Note de transparence.** Ce rapport a ete produit par Beaume "
        "a titre d'assistance. Il doit etre verifie par un avocat. Les "
        "citations marquees comme valides ont ete confrontees au corpus "
        "legal local. Les autres ont ete rejetees.",
        "",
    ]
    return "\n".join(lignes)
