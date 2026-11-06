# État du projet — 7 novembre 2026

Beaume est un prototype en recherche et développement. L'objectif est une première expérience vérifiable avec des avocats ; aucun résultat disponible ne démontre une aptitude à l'analyse autonome de dossiers professionnels.

## Dépôt public

| Élément | Ce qui est disponible | Limite |
| --- | --- | --- |
| Analyse documentaire | Lecture de PDF textuels, découpage, analyse et rapport Markdown | Le parcours résumé puis clic sur la source d'un fait n'est pas intégré de bout en bout |
| Démonstration autonome | PDF et corpus fictifs avec réponse fixe | Ce n'est pas une évaluation d'un modèle ni du droit réel |
| Références juridiques | Recherche et vérification selon le corpus et la date fournis | La présence d'un article ne démontre pas son applicabilité |
| Provenance | Contrôles de fichiers et de pages déclarés pour des citations | Une page existante ne démontre pas qu'un passage étaye une affirmation |
| Données | Corpus et poids de modèles séparés du clone | Leur disponibilité, couverture et licences doivent être contrôlées |
| Formats | PDF avec texte extractible | OCR des scans non intégré au parcours nominal |

Les états du rapport décrivent des contrôles logiciels. Ils ne certifient ni l'exhaustivité ni la justesse juridique.

## Travaux locaux en cours

Le laboratoire expérimente le Balladeur pour construire et examiner des dossiers synthétiques, ainsi que la conservation de plusieurs propositions de sources et une navigation expérimentale vers des pages PDF. Ces travaux ne sont pas tous publiés ou raccordés à l'application. Leur existence ne démontre pas une généralisation, l'indépendance complète des jeux ni l'aptitude à entraîner un modèle. La localisation d'un passage et son lien avec l'affirmation restent des contrôles distincts.

L'objectif immédiat est de raccorder progressivement résumé, informations et sources, avec des états explicites lorsque la recherche échoue ou reste ambiguë. La navigation et la conservation de l'identité du document doivent être testées dans les conditions d'utilisation.

## Points à démontrer avant un essai professionnel

- Pertinence du résumé et qualité des liens entre faits et passages.
- Comportement sur les documents incomplets, contradictoires et non lisibles.
- Installation, performances et ressources sur une configuration cible.
- Configuration locale, accès aux fichiers, journaux et flux réseau.
- Utilité réelle et compréhension des incertitudes par des avocats volontaires.

Les tests logiciels ne remplacent pas les évaluations indépendantes ni la revue métier. Voir [tests](TESTS.md), [recherche](AUDIT_RECHERCHE.md) et [validation juridique](VALIDATION_JURIDIQUE.md).
