"""Construction des prompts envoyes au LLM."""
from datetime import date

from beaume.legal.model import Article


INSTRUCTION_SYSTEME = """Tu es un assistant juridique francais rigoureux.

REGLES ABSOLUES :
1. Tu ne cites QUE les articles fournis dans la section ARTICLES DISPONIBLES.
2. Tu ne dois JAMAIS inventer un article, un numero ou un texte de loi.
3. Si aucun article n'est pertinent, tu ne cites rien.
4. Tu produis ta reponse UNIQUEMENT en JSON valide.
5. Toute citation doit inclure : code, numero, extrait.
6. La date_reference est celle fournie dans la section DATE DE REFERENCE.

FORMAT DE SORTIE (JSON strict) :
{
  "contexte": "Resume factuel du dossier en 2-3 phrases.",
  "parties": ["Nom ou role des parties"],
  "demandes": ["Ce qui est demande"],
  "problemes_juridiques": ["Question juridique identifiee"],
  "citations": [
    {
      "code": "code_travail",
      "numero": "L. 1234-1",
      "date_reference": "2024-01-01",
      "extrait": "Phrase precise de l'article applicable."
    }
  ]
}
"""


def _formater_articles(articles: list[Article], date_ref: date) -> str:
    if not articles:
        return "(aucun article disponible)"
    lignes = []
    for a in articles:
        version = a.version_a(date_ref)
        if version is None:
            continue
        lignes.append(
            f"- code: {a.code.value} | numero: {a.numero}\n"
            f"  texte: {version.texte}"
        )
    return "\n".join(lignes) if lignes else "(aucun article disponible)"


def construire_prompt(
    texte_dossier: str,
    articles: list[Article],
    date_reference: date,
) -> str:
    articles_formates = _formater_articles(articles, date_reference)
    return (
        f"{INSTRUCTION_SYSTEME}\n"
        f"=== DATE DE REFERENCE ===\n"
        f"{date_reference.isoformat()}\n\n"
        f"=== ARTICLES DISPONIBLES ===\n"
        f"{articles_formates}\n\n"
        f"=== DOSSIER CLIENT ===\n"
        f"{texte_dossier}\n\n"
        f"=== REPONSE JSON ===\n"
    )
