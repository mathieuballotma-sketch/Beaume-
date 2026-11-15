# État du projet — 15 novembre 2026

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

## Prototypes séparés

Le [laboratoire](../laboratoire/README.md) contient un parcours expérimental sur PDF fictif avec journal des étapes, détection de certains signaux et interface OCR Apple Vision. Ce parcours est séparé du pipeline principal, qui n'intègre pas l'OCR. Le laboratoire contient également une expérimentation de calcul matriciel CPU et Metal : ce n'est pas un moteur de calcul pour LLM. Le prototype de génération utilise `llama.cpp`, et non un moteur d'inférence propre à Beaume.

Les essais et leurs limites sont décrits avec le code. Les poids des modèles et les corpus juridiques réels ne sont pas publiés. Une exécution locale ou un test réussi ne prouve pas la sécurité ou la fidélité générale.

## Points à démontrer avant un essai professionnel

- Pertinence du résumé et qualité des liens entre faits et passages.
- Comportement sur les documents incomplets, contradictoires et non lisibles.
- Installation, performances et ressources sur une configuration cible.
- Configuration locale, accès aux fichiers, journaux et flux réseau.
- Utilité réelle et compréhension des incertitudes par des avocats volontaires.

Les tests logiciels ne remplacent pas les évaluations indépendantes ni la revue métier. Voir [tests](TESTS.md), [recherche](AUDIT_RECHERCHE.md) et [validation juridique](VALIDATION_JURIDIQUE.md).
