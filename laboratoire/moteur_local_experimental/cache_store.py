"""CacheStore — gestion securisee du cache de prompt llama.cpp.

Le fichier de cache contient l'etat KV du prompt. Il doit etre :
- cree en 0600 avant llama-completion (evite umask 022) ;
- verrouille avec flock pour eviter la concurrence (POSIX uniquement) ;
- isole par (hash modele tenant compte taille/mtime, hash prefixe) ;
- purge par LRU, sans supprimer un fichier en cours d'utilisation ;
- desactive par defaut.

Limites assumees :
- non chiffre : contient des IDs de tokens decodables par un tokenizer ;
- POSIX uniquement (fcntl) ; sur Windows, mode != 'disabled' leve RuntimeError ;
- la detection de remplacement du modele repose sur (taille, mtime) ;
  un remplacement par un fichier de meme taille et meme mtime passerait,
  et c'est le fingerprint interne de llama.cpp qui trancherait (via retry).
"""
from __future__ import annotations
import hashlib
import os
import platform
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

try:
    import fcntl
except ImportError:
    fcntl = None

MAX_FICHIERS = 5
MAX_OCTETS = 500 * 1024 * 1024  # 500 Mo (un cache a contexte 8192 pese ~44 Mo)


def _exiger_posix():
    if fcntl is None:
        raise RuntimeError(
            "CacheStore utilise fcntl (POSIX uniquement). "
            "Sur Windows, utiliser cache_mode='disabled' ou implementer "
            "un verrou via msvcrt.locking."
        )


def repertoire_cache() -> Path:
    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Caches"
    elif platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "beaume"


def hash_modele(chemin_modele: str) -> str:
    """Hash tenant compte du chemin, de la taille et du mtime.

    Detecte un remplacement courant du fichier au meme chemin. Ne detecte pas
    un remplacement par un fichier de meme taille et meme mtime (rare).
    Le fingerprint interne de llama.cpp reste la protection finale.
    """
    p = Path(chemin_modele)
    st = p.stat()
    payload = f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}".encode()
    return hashlib.sha256(payload).hexdigest()[:12]


class CacheStore:
    def __init__(self, mode: str = "disabled"):
        if mode not in ("disabled", "auto", "enabled"):
            raise ValueError("mode invalide : " + mode)
        if mode != "disabled":
            _exiger_posix()
        self.mode = mode
        self.base = repertoire_cache()

    def chemin(self, chemin_modele: str, prefixe: str) -> Optional[Path]:
        if self.mode == "disabled":
            return None
        h_mod = hash_modele(chemin_modele)
        h_pre = hashlib.sha256(prefixe.encode()).hexdigest()[:12]
        self.base.mkdir(parents=True, exist_ok=True)
        return self.base / ("prompt_" + h_mod + "_" + h_pre + ".bin")

    @contextmanager
    def ouvert(self, chemin: Optional[Path]):
        if chemin is None:
            yield None
            return
        chemin.touch(mode=0o600, exist_ok=True)
        os.chmod(chemin, 0o600)
        fd = os.open(str(chemin), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield chemin
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def purger(self) -> dict:
        """Purge LRU. Skip les fichiers verrouilles (en cours d'utilisation).

        Retourne un dict {supprimes, ignores_verrouilles, total_octets}.
        """
        resultat = {"supprimes": 0, "ignores_verrouilles": 0, "total_octets": 0}
        if not self.base.exists():
            return resultat
        fichiers = sorted(
            self.base.glob("prompt_*.bin"),
            key=lambda p: p.stat().st_mtime,
        )
        total = sum(p.stat().st_size for p in fichiers)
        for p in list(fichiers):
            if len(fichiers) <= MAX_FICHIERS and total <= MAX_OCTETS:
                break
            try:
                fd = os.open(str(p), os.O_RDWR)
            except OSError:
                continue
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (BlockingIOError, OSError):
                    resultat["ignores_verrouilles"] += 1
                    os.close(fd)
                    continue
                taille = p.stat().st_size
                p.unlink()
                total -= taille
                resultat["supprimes"] += 1
                fichiers.remove(p)
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except OSError:
                try:
                    os.close(fd)
                except OSError:
                    pass
        resultat["total_octets"] = total
        return resultat
