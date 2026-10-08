"""Erreurs metier du domaine juridique."""


class BeaumeError(Exception):
    """Base de toutes les erreurs Beaume."""


class ArticleIntrouvable(BeaumeError):
    """L'article demande n'existe pas dans le corpus."""


class VersionIntrouvable(BeaumeError):
    """L'article existe mais aucune version ne couvre la date demandee."""


class IdentifiantInvalide(BeaumeError):
    """L'identifiant Legifrance ne respecte pas le format attendu."""


class CitationRejetee(BeaumeError):
    """La citation a ete rejetee par le verificateur."""
