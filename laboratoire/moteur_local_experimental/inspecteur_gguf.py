"""Lecture locale des métadonnées GGUF ; ne charge ni n'exécute de modèle.

Dépendance : bibliothèque gguf de llama.cpp. Cette fiche ne qualifie pas un
modèle et ne prédit pas la RAM requise pour l'inférence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


class InspectionImpossible(Exception):
    """Modèle inaccessible, illisible ou lecteur GGUF indisponible."""


def inspecter_modele(chemin: str | Path, *, empreinte: bool = False,
                     lecteur: Callable | None = None) -> dict[str, Any]:
    """Renvoie une fiche factuelle ; les métadonnées absentes restent nulles."""
    path = Path(chemin).expanduser().resolve()
    try:
        if not path.is_file():
            raise InspectionImpossible(f"Fichier introuvable : {path}")
        with path.open('rb') as f:
            if f.read(4) != b'GGUF':
                raise InspectionImpossible("Le fichier ne porte pas la signature GGUF.")
        if lecteur is None:
            try:
                from gguf import GGUFReader
            except ImportError as exc:
                raise InspectionImpossible("Bibliothèque gguf absente de l'environnement Python.") from exc
            lecteur = GGUFReader
        obj = lecteur(str(path))
        def champ(key: str):
            field = obj.fields.get(key)
            if field is None:
                return None
            value = field.contents()
            return value.item() if hasattr(value, 'item') else value
        arch = champ('general.architecture')
        if not isinstance(arch, str):
            arch = None
        def arch_champ(nom: str):
            return champ(f'{arch}.{nom}') if arch else None
        elements = sum(int(t.n_elements) for t in obj.tensors)
        result = {
            'schema': 'beaume.fiche_gguf.v1',
            'fichier': str(path), 'taille_octets': path.stat().st_size,
            'sha256': None, 'architecture': arch, 'nom': champ('general.name'),
            'type_fichier_gguf_code': champ('general.file_type'),
            'parametres_declares': champ('general.parameter_count'),
            'elements_tenseurs': elements, 'nombre_tenseurs': len(obj.tensors),
            'contexte_entraine_tokens': arch_champ('context_length'),
            'nombre_couches': arch_champ('block_count'),
            'dimension_embedding': arch_champ('embedding_length'),
            'template_chat_present': 'tokenizer.chat_template' in obj.fields,
            'ram_inference_requise_octets': None,
            'qualification_taches': 'non_evaluee',
            'avertissement': ('Les metadonnees decrivent le fichier ; elles ne garantissent '
                              'ni compatibilite, ni performance, ni fiabilite. La RAM '
                              'necessaire depend notamment du contexte et du backend.'),
        }
        if empreinte:
            digest = hashlib.sha256()
            with path.open('rb') as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    digest.update(block)
            result['sha256'] = digest.hexdigest()
        return result
    except InspectionImpossible:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, EOFError) as exc:
        raise InspectionImpossible(f'Lecture GGUF impossible : {exc}') from exc


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspecter localement un modèle GGUF.')
    parser.add_argument('modele', help='Chemin du fichier modèle')
    parser.add_argument('--sha256', action='store_true', help='Calculer l’empreinte du fichier entier')
    args = parser.parse_args()
    try:
        print(json.dumps(inspecter_modele(args.modele, empreinte=args.sha256), ensure_ascii=False, indent=2))
    except InspectionImpossible as exc:
        parser.exit(1, f'Inspection impossible : {exc}\n')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
