"""Decoupage d'un texte en chunks exploitables.

Fonction pure : aucune I/O, aucun effet de bord.
Loi 6 : purete au coeur, effets aux bords.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    index: int
    texte: str
    debut_car: int
    fin_car: int

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


def decouper(
    texte: str,
    taille_cible: int = 600,
    chevauchement: int = 80,
) -> list[Chunk]:
    if not texte or not texte.strip():
        return []
    if taille_cible <= 0:
        raise ValueError("taille_cible doit etre > 0")
    if chevauchement < 0 or chevauchement >= taille_cible:
        raise ValueError("chevauchement doit etre dans [0, taille_cible[")

    paragraphes = _decouper_paragraphes(texte)
    if not paragraphes:
        return []

    chunks: list[Chunk] = []
    tampon_debut: int | None = None
    tampon_fin: int = 0

    def _flush() -> None:
        nonlocal tampon_debut, tampon_fin
        if tampon_debut is None:
            return
        morceau = texte[tampon_debut:tampon_fin]
        chunks.append(Chunk(
            index=len(chunks),
            texte=morceau,
            debut_car=tampon_debut,
            fin_car=tampon_fin,
        ))
        tampon_debut = None
        tampon_fin = 0

    for debut, fin in paragraphes:
        longueur_paragraphe = fin - debut
        if longueur_paragraphe > taille_cible:
            _flush()
            pos = debut
            while pos < fin:
                chunks.append(Chunk(
                    index=len(chunks),
                    texte=texte[pos:min(pos + taille_cible, fin)],
                    debut_car=pos,
                    fin_car=min(pos + taille_cible, fin),
                ))
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
    return chunks
