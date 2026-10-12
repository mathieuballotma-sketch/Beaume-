"""Mapping : noms de codes DILA -> enum CodeJuridique.

Le dataset Hugging Face utilise les noms officiels des codes
("Code civil", "Code du travail"...). On les convertit vers notre
enum interne.
"""
from beaume.legal.model import CodeJuridique


# Mapping titre DILA -> CodeJuridique
_TITRE_VERS_CODE: dict[str, CodeJuridique] = {
    "Code civil": CodeJuridique.CODE_CIVIL,
    "Code pénal": CodeJuridique.CODE_PENAL,
    "Code du travail": CodeJuridique.CODE_TRAVAIL,
    "Code de commerce": CodeJuridique.CODE_COMMERCE,
    "Code de la consommation": CodeJuridique.CODE_CONSOMMATION,
    "Code de la sécurité sociale": CodeJuridique.CODE_SECURITE_SOCIALE,
    "Code de procédure civile": CodeJuridique.CODE_PROCEDURE_CIVILE,
    "Code de procédure pénale": CodeJuridique.CODE_PROCEDURE_PENALE,
    "Code de la santé publique": CodeJuridique.CODE_SANTE_PUBLIQUE,
    "Code rural et de la pêche maritime": CodeJuridique.CODE_RURAL,
    "Code des transports": CodeJuridique.CODE_TRANSPORTS,
    "Code de l'environnement": CodeJuridique.CODE_ENVIRONNEMENT,
    "Code général des collectivités territoriales":
        CodeJuridique.CODE_COLLECTIVITES_TERRITORIALES,
    "Code monétaire et financier": CodeJuridique.CODE_MONETAIRE_FINANCIER,
    "Code de l'éducation": CodeJuridique.CODE_EDUCATION,
    "Code de la construction et de l'habitation":
        CodeJuridique.CODE_CONSTRUCTION_HABITATION,
    "Code de l'action sociale et des familles":
        CodeJuridique.CODE_ACTION_SOCIALE_FAMILLES,
    "Code de la défense": CodeJuridique.CODE_DEFENSE,
    "Code général de la fonction publique":
        CodeJuridique.CODE_FONCTION_PUBLIQUE,
    "Code de l'énergie": CodeJuridique.CODE_ENERGIE,
    "Code de la sécurité intérieure": CodeJuridique.CODE_SECURITE_INTERIEURE,
    "Code de l'entrée et du séjour des étrangers et du droit d'asile":
        CodeJuridique.CODE_ETRANGERS,
    "Code de l'urbanisme": CodeJuridique.CODE_URBANISME,
}


def code_depuis_titre(titre: str | None) -> CodeJuridique:
    """Retourne le CodeJuridique correspondant au titre DILA.

    Si le titre n'est pas reconnu, retourne CODE_AUTRE.
    """
    if not titre:
        return CodeJuridique.CODE_AUTRE
    return _TITRE_VERS_CODE.get(titre.strip(), CodeJuridique.CODE_AUTRE)


def codes_reconnus() -> list[str]:
    """Retourne la liste des titres DILA reconnus."""
    return sorted(_TITRE_VERS_CODE.keys())
