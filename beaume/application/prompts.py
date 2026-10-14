"""Construction des prompts envoyes au LLM."""
from datetime import date

from beaume.legal.model import Article


INSTRUCTION_SYSTEME = """Tu es un assistant juridique francais rigoureux.

REGLES ABSOLUES :
1. Tu ne cites QUE les articles fournis dans la section ARTICLES DISPONIBLES.
2. Tu ne dois JAMAIS inventer un article, un numero ou un texte de loi.
3. Si aucun article n'est pertinent, la liste "citations" doit etre VIDE ([]).
4. Tu produis UNIQUEMENT un objet JSON. Pas de texte avant. Pas de texte apres.
5. Le JSON contient EXACTEMENT ces 5 cles, dans cet ordre :
   "contexte", "parties", "demandes", "problemes_juridiques", "citations".
6. N'invente JAMAIS d'autres cles. Sont INTERDITES notamment : "rep",
   "conclusion", "analyse", "resume", "synthese", "recommandation".
7. Chaque element de "citations" contient EXACTEMENT 3 cles :
   "code", "numero", "extrait"."""


# Exemple volontairement sur un AUTRE domaine (responsabilite civile)
# pour eviter que le LLM recopie l'exemple au lieu de repondre au dossier.
EXEMPLE_SORTIE = """{
  "contexte": "Un pieton blesse par un vehicule demande reparation.",
  "parties": ["M. Martin", "Mme Leroy"],
  "demandes": ["Indemnisation du prejudice corporel"],
  "problemes_juridiques": ["Responsabilite civile pour fait personnel"],
  "citations": [
    {
      "code": "code_civil",
      "numero": "1240",
      "extrait": "Tout fait quelconque de l'homme, qui cause a autrui un dommage, oblige celui par la faute duquel il est arrive a le reparer."
    }
  ]
}"""


RAPPEL_FORMAT = """Reponds UNIQUEMENT avec un objet JSON valide contenant
EXACTEMENT les 5 cles suivantes :
  - "contexte"             : string (2-3 phrases factuelles)
  - "parties"              : liste de strings
  - "demandes"             : liste de strings
  - "problemes_juridiques" : liste de strings
  - "citations"            : liste d'objets, chacun avec EXACTEMENT :
      "code"    : string (ex: "code_travail")
      "numero"  : string (ex: "L. 1233-3")
      "extrait" : string (phrase EXACTE recopiee de l'article)

Aucune autre cle. Aucun texte autour du JSON. Si aucun article n'est
pertinent, "citations" doit etre []. Termine imperativement par "}".
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
        f"{INSTRUCTION_SYSTEME}\n\n"
        f"=== EXEMPLE DE FORMAT ATTENDU ===\n"
        f"{EXEMPLE_SORTIE}\n\n"
        f"=== DATE DE REFERENCE ===\n"
        f"{date_reference.isoformat()}\n\n"
        f"=== ARTICLES DISPONIBLES ===\n"
        f"{articles_formates}\n\n"
        f"=== DOSSIER CLIENT ===\n"
        f"{texte_dossier}\n\n"
        f"=== RAPPEL DU FORMAT (a respecter strictement) ===\n"
        f"{RAPPEL_FORMAT}\n"
        f"=== REPONSE JSON ===\n"
    )
