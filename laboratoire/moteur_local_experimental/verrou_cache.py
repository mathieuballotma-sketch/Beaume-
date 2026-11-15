"""verrou_cache.py — Enveloppe de premier_moteur qui refuse le cache de prompt.

Motif (voir coordination_beaume/ETAT_ACTUEL.md et instruction #6) :
- les fichiers de cache llama.cpp peuvent contenir les identifiants des tokens
  du prompt complet, y compris des faits du dossier ;
- CacheStore n'applique pas 0o600 aux fichiers écrits via prompt_cache= ;
- cache_A.bin et cache_B.bin ont été observés en 0644 dans /private/tmp ;
- cache en RAM non analysé.

Le parcours de production active donc zero cache : ni cache_mode enabled/auto,
ni prompt_cache=.

Ne modifie PAS les fichiers historiques cache_store.py / generateur_llama_cpp.py.
Les anciens fichiers cache ne sont pas supprimés par ce module.
"""

from __future__ import annotations

from typing import Any

_PARAMS_INTERDITS = frozenset({
    "prompt_cache", "cache_mode", "cache_path",
})
_VALEURS_ACCEPTEES = frozenset({None, "disabled", False, ""})


class CacheInterdit(RuntimeError):
    """Refus d'activer un cache de prompt dans le parcours construit."""


def _verifier_kwargs(kwargs: dict[str, Any]) -> None:
    for cle in _PARAMS_INTERDITS:
        if cle in kwargs and kwargs[cle] not in _VALEURS_ACCEPTEES:
            raise CacheInterdit(
                f"Parametre {cle!r}={kwargs[cle]!r} interdit dans le parcours : "
                "le cache de prompt peut contenir les identifiants des tokens "
                "du prompt complet (faits du dossier). Voir "
                "coordination_beaume/ETAT_ACTUEL.md et instruction #6. "
                "Aucun cache n'est activable dans le parcours construit."
            )


def appel_modele_sans_cache(*args: Any, **kwargs: Any):
    """Delegue a premier_moteur.executer_llama_completion apres refus du cache."""
    _verifier_kwargs(kwargs)
    from premier_moteur import executer_llama_completion as _reel
    return _reel(*args, **kwargs)
