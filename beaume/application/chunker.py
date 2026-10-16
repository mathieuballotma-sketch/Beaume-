"""Decoupage d'un texte en chunks exploitables.

Fonction pure : aucune I/O, aucun effet de bord.
Loi 6 : purete au coeur, effets aux bords.
"""
from __future__ import annotations

from dataclasses import dataclass

from beaume.ports.extracteur import PageExtraite


@dataclass(frozen=True)
class Chunk:
    index: int
    texte: str
    debut_car: int
    fin_car: int
    fichier: str = ""
    page_debut: int = 0
    page_fin: int = 0

    @property
    def longueur(self) -> int:
        return len(self.texte)


def _decouper_paragraphes(texte: str) -> list[tuple[int, int]]:
    bornes: list[tuple[int, int]] = []
    debut = 0
    i = 0
    n = len(texte)
    while i < n:
        if texte.startswith("\n\n", i):
            if i > debut:
                bornes.append((debut, i))
            i += 2
            debut = i
        else:
            i += 1
    if debut < n:
        bornes.append((debut, n))
    return [(d, f) for d, f in bornes if texte[d:f].strip()]


def _offsets_des_chunks(
    texte: str,
    taille_cible: int,
    chevauchement: int,
) -> list[tuple[int, int]]:
    """Retourne la liste des (debut, fin) de chaque chunk dans le texte."""
    paragraphes = _decouper_paragraphes(texte)
    if not paragraphes:
        return []

    offsets: list[tuple[int, int]] = []
    tampon_debut: int | None = None
    tampon_fin: int = 0

    def _flush() -> None:
        nonlocal tampon_debut, tampon_fin
        if tampon_debut is None:
            return
        offsets.append((tampon_debut, tampon_fin))
        tampon_debut = None
        tampon_fin = 0

    for debut, fin in paragraphes:
        longueur_paragraphe = fin - debut
        if longueur_paragraphe > taille_cible:
            _flush()
            pos = debut
            while pos < fin:
                offsets.append((pos, min(pos + taille_cible, fin)))
                pos += taille_cible - chevauchement
            continue

        if tampon_debut is None:
            tampon_debut = debut
            tampon_fin = fin
            continue

        taille_avec = fin - tampon_debut
        if taille_avec <= taille_cible:
            tampon_fin = fin
        else:
            _flush()
            recul = max(tampon_fin - chevauchement, 0)
            tampon_debut = recul if recul < debut else debut
            tampon_fin = fin

    _flush()
    return offsets


def _pages_du_chunk(
    pages: list[PageExtraite],
    debut: int,
    fin: int,
) -> tuple[int, int]:
    """Retourne (page_debut, page_fin) pour un chunk [debut, fin[.

    Un chunk peut chevaucher plusieurs pages si le decoupage le coupe.
    """
    if not pages:
        return (0, 0)
    page_debut: int | None = None
    page_fin: int | None = None
    for p in pages:
        if p.fin_car > debut and page_debut is None:
            page_debut = p.numero
        if p.debut_car < fin:
            page_fin = p.numero
    if page_debut is None:
        page_debut = pages[0].numero
    if page_fin is None:
        page_fin = page_debut
    return (page_debut, page_fin)


def _valider_params(taille_cible: int, chevauchement: int) -> None:
    if taille_cible <= 0:
        raise ValueError("taille_cible doit etre > 0")
    if chevauchement < 0 or chevauchement >= taille_cible:
        raise ValueError("chevauchement doit etre dans [0, taille_cible[")


def decouper(
    texte: str,
    taille_cible: int = 600,
    chevauchement: int = 80,
) -> list[Chunk]:
    """Decoupe un texte brut en chunks (interface historique).

    Les chunks n'ont pas d'information de page. Utiliser
    `decouper_pages` pour conserver les pages.
    """
    if not texte or not texte.strip():
        return []
    _valider_params(taille_cible, chevauchement)

    offsets = _offsets_des_chunks(texte, taille_cible, chevauchement)
    return [
        Chunk(
            index=i,
            texte=texte[d:f],
            debut_car=d,
            fin_car=f,
        )
        for i, (d, f) in enumerate(offsets)
    ]


def decouper_pages(
    pages: list[PageExtraite],
    fichier: str,
    taille_cible: int = 600,
    chevauchement: int = 80,
) -> list[Chunk]:
    """Decoupe un document pagine en chunks annotes.

    Chaque chunk porte :
      - `fichier`     : nom du fichier source
      - `page_debut`  : numero de la premiere page couverte
      - `page_fin`    : numero de la derniere page couverte
    """
    if not pages:
        return []
    texte = "\n\n".join(p.texte for p in pages)
    if not texte.strip():
        return []
    _valider_params(taille_cible, chevauchement)

    offsets = _offsets_des_chunks(texte, taille_cible, chevauchement)
    chunks: list[Chunk] = []
    for i, (d, f) in enumerate(offsets):
        page_debut, page_fin = _pages_du_chunk(pages, d, f)
        chunks.append(Chunk(
            index=i,
            texte=texte[d:f],
            debut_car=d,
            fin_car=f,
            fichier=fichier,
            page_debut=page_debut,
            page_fin=page_fin,
        ))
    return chunks
    return chunks
