"""Construction des prompts envoyes au LLM.

Principe de conception (2026-10-16) :
- Prompt COURT (~500 tokens) : Qwen 7B decroche apres ~750 tokens.
- DOSSIER D'ABORD, regles ensuite : les petits modeles respectent
  mieux les instructions placees en fin de contexte.
- Le JSON est force par le mode `format` d'Ollama, pas par le prompt.
"""
from datetime import date

from beaume.legal.model import Article


# Prompt systeme court. 3 regles seulement.
# Le format JSON est garanti par le schema passe a Ollama.
INSTRUCTION_SYSTEME = """Tu es un assistant juridique francais.

Tu produis UNIQUEMENT un objet JSON. Pas de texte avant. Pas de
texte apres. Pas de commentaire.

Trois regles :
1. Tu ne cites QUE les articles fournis dans ARTICLES DISPONIBLES.
   Tu n'inventes JAMAIS un article.
2. "extrait" = COPIE LITTERALE d'une phrase de l'article. Jamais de
   reformulation. Si tu ne peux pas copier, ne cite pas.
3. "pages" et "fichier" = source dans le dossier. Le dossier contient
   des en-tetes [nom.pdf, page X]. Utilise-les."""


# Exemple unique et court.
EXEMPLE_SORTIE = """{
  "contexte": "M. X a ete licencie par la societe Y.",
  "parties": ["M. X", "Societe Y"],
  "demandes": ["Contester le licenciement"],
  "problemes_juridiques": ["Licenciement sans cause reelle"],
  "citations": [{
    "code": "code_travail",
    "numero": "L. 1235-3",
    "extrait": "Si le licenciement d'un salarie survient pour une cause qui n'est pas reelle et serieuse...",
    "pages": [3],
    "fichier": "conclusions.pdf"
  }]
}"""


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
    """Construit le prompt dans l'ordre : dossier -> articles -> regles."""
    articles_formates = _formater_articles(articles, date_reference)
    return (
        f"{INSTRUCTION_SYSTEME}\n\n"
        f"=== DOSSIER CLIENT ===\n"
        f"{texte_dossier}\n\n"
        f"=== ARTICLES DISPONIBLES ===\n"
        f"{articles_formates}\n\n"
        f"=== DATE DE REFERENCE ===\n"
        f"{date_reference.isoformat()}\n\n"
        f"=== EXEMPLE DE SORTIE ===\n"
        f"{EXEMPLE_SORTIE}\n\n"
        f"=== REPONSE (JSON uniquement) ===\n"
    )