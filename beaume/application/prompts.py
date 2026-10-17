"""Construction des prompts envoyes au LLM.

Principes de conception (2026-10-16) :
- Prompt COURT (~400 tokens) : Qwen 7B decroche apres ~750 tokens.
- DOSSIER D'ABORD, regles ensuite : les petits modeles respectent
  mieux les instructions placees en fin de contexte.
- PAS D'EXEMPLE JSON dans le prompt : Qwen 7B recopie l'exemple au
  lieu de lire le dossier (bug identifie le 2026-10-16).
- Le JSON est force par le mode `format` d'Ollama (schema), pas par
  le prompt.
- "fichier" et "pages" sont contraints par le schema (enum sur les
  vrais noms et sur les pages reelles). Qwen met "" partout sinon.
"""
from datetime import date

from beaume.legal.model import Article


INSTRUCTION_SYSTEME = """Tu es un assistant juridique francais.

Tu produis UNIQUEMENT un objet JSON. Pas de texte avant. Pas de
texte apres. Pas de commentaire.

REGLES (dans l'ordre d'importance) :

1. Le "contexte" resume LE DOSSIER CI-DESSOUS. Tu ne recopies JAMAIS
   une phrase d'exemple. Tu decris les faits reels du dossier.

2. Tu ne cites QUE les articles fournis dans ARTICLES DISPONIBLES.
   Tu n'inventes JAMAIS un article, un numero ou un texte de loi.

3. "code" = UNIQUEMENT le nom du code, choisi dans la liste
   autorisee (par exemple "code_travail", "code_civil"). Ne mets
   JAMAIS le numero dans "code".

4. "numero" = UNIQUEMENT le numero de l'article (par exemple
   "L. 1235-3"). Ne mets JAMAIS le nom du code dans "numero".

5. "extrait" = COPIE LITTERALE d'une phrase de l'article, mot pour
   mot. Jamais de reformulation. Si tu ne peux pas copier exactement,
   ne cite pas l'article.

6. "fichier" = OBLIGATOIRE. Choisis un nom exact dans la LISTE DES
   FICHIERS ci-dessus. Le dossier contient des en-tetes comme
   "[bulletins_salaire.pdf, page 1]" avant chaque paragraphe.
   Recopie le nom du fichier d'ou vient l'extrait. Ne mets JAMAIS "".

7. "pages" = OBLIGATOIRE. Liste non vide de numeros de page, choisis
   parmi les entiers presents dans les en-tetes [nom.pdf, page X].
   Ne mets JAMAIS []."""


def _formater_articles(articles: list[Article], date_ref: date) -> str:
    lignes = []
    for a in articles:
        v = a.version_a(date_ref)
        if v is None:
            continue
        lignes.append(f"- {a.code.value} {a.numero} : {v.texte}")
    return "\n".join(lignes) if lignes else "(aucun article disponible)"


def _formater_liste_fichiers(fichiers: tuple[str, ...]) -> str:
    if not fichiers:
        return "(aucun fichier)"
    return "\n".join(f"- {nom}" for nom in fichiers)


def construire_prompt(
    texte_dossier: str,
    articles: list[Article],
    date_reference: date,
    fichiers_disponibles: tuple[str, ...] = (),
) -> str:
    """Construit le prompt dans l'ordre :
    1. Instructions systeme (courtes)
    2. Liste des fichiers du dossier
    3. Dossier client (avec en-tetes [fichier, page X])
    4. Articles disponibles
    5. Date de reference
    """
    articles_formates = _formater_articles(articles, date_reference)
    fichiers_formates = _formater_liste_fichiers(fichiers_disponibles)
    return (
        f"{INSTRUCTION_SYSTEME}\n\n"
        f"=== LISTE DES FICHIERS DU DOSSIER ===\n"
        f"{fichiers_formates}\n\n"
        f"=== DOSSIER CLIENT ===\n"
        f"{texte_dossier}\n\n"
        f"=== ARTICLES DISPONIBLES ===\n"
        f"{articles_formates}\n\n"
        f"=== DATE DE REFERENCE ===\n"
        f"{date_reference.isoformat()}\n\n"
        f"=== REPONSE (JSON uniquement) ===\n"
    )