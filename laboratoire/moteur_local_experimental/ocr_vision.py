"""ocr_vision.py — OCR via Vision framework (Apple), binaire Swift compile.

Local uniquement. Aucune connexion. Le binaire est compile depuis vision_ocr.swift
dans bin/vision_ocr. Retourne texte concatene des lignes reconnues, ou leve
RuntimeError si le binaire est absent ou echoue.
"""
from __future__ import annotations
import os
import pathlib
import subprocess
import tempfile

BIN = pathlib.Path(__file__).parent / "bin" / "vision_ocr"


def ocr_image(chemin_image, timeout=60, retour_coordonnees=False):
    if not BIN.is_file():
        raise RuntimeError("binaire vision_ocr absent : " + str(BIN))
    r = subprocess.run(
        [str(BIN), str(chemin_image)],
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError("vision_ocr code " + str(r.returncode) + " : " + (r.stdout or r.stderr)[:200])
    lignes = []
    bboxes = []
    for l in r.stdout.splitlines():
        if l.startswith("LINE|"):
            parts = l.split("|", 3)
            if len(parts) == 4:
                lignes.append(parts[3])
                if retour_coordonnees:
                    try:
                        x, y, w, h = (float(v) for v in parts[2].split(","))
                        bboxes.append({
                            "confiance": float(parts[1]),
                            "x": x, "y": y, "largeur": w, "hauteur": h,
                            "texte": parts[3],
                        })
                    except (ValueError, IndexError):
                        pass
    texte = " ".join(lignes)
    if retour_coordonnees:
        return texte, bboxes
    return texte


def ocr_page_image(fitz_page, dpi=200, retour_coordonnees=False):
    import fitz
    pix = fitz_page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        pix.save(tmp)
        return ocr_image(tmp, retour_coordonnees=retour_coordonnees)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
