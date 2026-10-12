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


def _formater_verification(v: ResultatVerification) -> str:
    c = v.citation
    lignes = [
        f"### {c.code.value} - Article {c.numero}",
        "",
        f"- **Date de reference** : {c.date_reference.isoformat()}",
    ]
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
    c = v.citation
    return (
        f"- **{c.code.value} - Article {c.numero}** "
        f"(au {c.date_reference.isoformat()}) : "
        f"{v.statut.value} - {v.message}"
    )


def rendre_markdown(rapport: Rapport) -> str:
    a = rapport.analyse
    lignes = [
        "# Rapport d'analyse - Beaume",
        "",
        f"- **Dossier** : `{rapport.dossier}`",
        f"- **Date de reference** : {rapport.date_reference.isoformat()}",
        f"- **Modele LLM** : {rapport.modele_llm}",
        f"- **Duree d'analyse** : {rapport.duree_s:.2f} s",
        f"- **Citations valides** : {len(rapport.citations_valides)}",
        f"- **Citations rejetees** : {len(rapport.citations_rejetees)}",
        "",
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
