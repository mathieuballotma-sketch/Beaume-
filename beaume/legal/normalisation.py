"""Normalisation des numeros d'articles.

Deux formats coexistent :
  - DILA   : "L1234-1", "R1234-1", "D1234-1" (compact)
  - Humain : "L. 1234-1", "R. 1234-1" (avec espaces et points)

On normalise tout vers le format DILA compact pour la recherche.
"""
import re


_PREFIXES = ("L", "R", "D")


def normaliser_numero(numero: str) -> str:
    """Convertit un numero en format DILA compact.

    Exemples :
        "L. 1234-1"   -> "L1234-1"
        "L 1234-1"    -> "L1234-1"
        "L1234-1"     -> "L1234-1"
        "R. 1234-1"   -> "R1234-1"
        "1240"        -> "1240"
        "Annexe 2"    -> "Annexe2"
    """
    if not numero:
        return ""
    # Retirer espaces, points, tirets de tete (mais garder le tiret interne)
    n = numero.strip()
    # Supprimer les espaces et points qui suivent une lettre de prefixe
    # "L. 1234-1" -> "L1234-1"
    n = re.sub(r"([LRD])\.\s*", r"\1", n)
    n = re.sub(r"([LRD])\s+", r"\1", n)
    # Supprimer tous les espaces restants
    n = n.replace(" ", "")
    return n


def format_humain(numero: str) -> str:
    """Convertit un numero DILA en format humain francais.

    Exemples :
        "L1234-1"  -> "L. 1234-1"
        "R1234-1"  -> "R. 1234-1"
        "1240"     -> "1240"
        "L1152-1"  -> "L. 1152-1"
    """
    if not numero:
        return ""
    n = numero.strip()
    # "L1234-1" -> "L. 1234-1"
    for prefixe in _PREFIXES:
        if n.startswith(prefixe) and len(n) > 1 and n[1].isdigit():
            return f"{prefixe}. {n[1:]}"
    return n


def egal_numero(a: str, b: str) -> bool:
    """Compare deux numeros en ignorant le format."""
    return normaliser_numero(a) == normaliser_numero(b)
