"""Utilitaires de traitement de texte.

Extraction de mots-cles pour la recherche plein-texte FTS5.
"""
import re
import unicodedata


# Stopwords francais : mots trop courants pour etre utiles en recherche.
STOPWORDS_FR = frozenset({
    "le", "la", "les", "un", "une", "des", "du", "de", "da", "das",
    "et", "ou", "mais", "donc", "or", "ni", "car",
    "a", "au", "aux", "en", "dans", "sur", "sous", "par", "pour",
    "avec", "sans", "vers", "chez", "entre", "contre", "depuis",
    "ce", "cet", "cette", "ces", "ceci", "cela", "celui", "celle",
    "il", "elle", "ils", "elles", "on", "nous", "vous", "je", "tu",
    "me", "te", "se", "lui", "leur", "leurs", "mon", "ma", "mes",
    "ton", "ta", "tes", "son", "sa", "ses", "notre", "nos", "votre",
    "vos", "est", "sont", "etait", "etaient", "sera", "seront",
    "ete", "avoir", "ayant", "eu", "fait", "faire", "faisant",
    "que", "qui", "quoi", "dont", "ou", "comment", "pourquoi",
    "quand", "si", "ne", "pas", "plus", "moins", "tres", "trop",
    "aussi", "encore", "deja", "toujours", "jamais", "souvent",
    "tout", "tous", "toute", "toutes", "meme", "memes", "autre",
    "autres", "tel", "telle", "tels", "telles", "quel", "quelle",
    "etre", "avoir", "donc", "alors", "ainsi", "comme", "y",
})

# Longueur minimale d'un mot pour etre considere comme mot-cle.
LONGUEUR_MIN = 3


def _retirer_accents(mot: str) -> str:
    """Retire les accents d'un mot (utilise pour comparaison)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", mot)
        if unicodedata.category(c) != "Mn"
    )


def extraire_mots_cles(texte: str, limite: int = 20) -> list[str]:
    """Extrait les mots-cles utiles d'un texte.

    - Retire la ponctuation.
    - Retire les stopwords.
    - Garde les mots de longueur >= LONGUEUR_MIN.
    - Deduplique (garde l'ordre d'apparition).
    - Limite a `limite` mots-cles.
    """
    if not texte:
        return []
    if limite <= 0:
        raise ValueError("limite doit etre > 0")

    # On normalise : minuscules, ponctuation -> espace.
    texte = texte.lower()
    texte = re.sub(r"[^\w\s]", " ", texte, flags=re.UNICODE)
    mots = texte.split()

    vus: set[str] = set()
    resultat: list[str] = []
    for mot in mots:
        if len(mot) < LONGUEUR_MIN:
            continue
        # On compare sans accents pour le stopword, mais on garde
        # la version originale pour la recherche.
        sans_accent = _retirer_accents(mot)
        if sans_accent in STOPWORDS_FR:
            continue
        if sans_accent in vus:
            continue
        vus.add(sans_accent)
        resultat.append(mot)
        if len(resultat) >= limite:
            break
    return resultat
