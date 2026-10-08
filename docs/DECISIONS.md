# Décisions techniques — Beaume

## 2026-10-08 — Arborescence
- Code dans `beaume/`, données dans `data/`.
- Chemins centralisés dans `beaume/config/paths.py`.
- Aucune donnée client dans git.

## 2026-10-08 — Logging
- Logger rotatif, 5 Mo × 5 fichiers, dans `data/logs/`.

## 2026-10-08 — Les 6 lois d'architecture
1. Dépendance descendante (couches L0->L5, jamais l'inverse)
2. Conservation de l'information (chaque transformation traçable)
3. Tiers exclu (machine à états fermée)
4. Inversion des dépendances (ports & adapters)
5. Composition fermée (une porte d'entrée par module)
6. Pureté au cœur, effets aux bords

## 2026-10-08 — Ontologie juridique
- Identifiant = LEGIARTI/LEGITEXT/JURITEXT + 12 chiffres
- Numéro humain (L. 1234-1) = alias, jamais identifiant
- Un article = plusieurs versions datées
- Une citation porte TOUJOURS une date de référence
- Immutabilité (frozen=True) sur les versions

## 2026-10-08 — Ports
- `Extracteur` : contrat unique pour tous les formats
- `RegistreExtracteurs` : ajout sans modification
- Aucun `if suffix == ".pdf"` dans le pipeline

## 2026-10-08 — Machine à états
- États : DEPOSE -> EXTRAIT -> DECOUPE -> INDEXE -> ANALYSE -> VERIFIE -> PUBLIE
- ECHEC accessible depuis n'importe quel état non terminal
- Transitions illégales = exception levée
- Historique horodaté conservé
