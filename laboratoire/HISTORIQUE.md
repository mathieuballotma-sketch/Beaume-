# Historique des travaux et raisons des choix

Synthèse établie le 14 novembre 2026 à partir des journaux et artefacts locaux. Les expériences ne figurent pas toutes dans ce dépôt : lorsqu'un résultat est décrit sans fichier associé, il s'agit d'une trace documentaire, non d'une expérience ici reproductible. Les corrections successives sont conservées dans les journaux locaux et ne sont pas toutes reproduites ci-dessous.

## Dossiers et données fictifs : Balladeur

**Problème :** tester un assistant juridique sans exploiter des dossiers confidentiels et sans supposer qu'un texte généré constitue un dossier réaliste. **Approche :** expérimenter la construction de scénarios et de pièces fictives avec des faits, dates et rôles identifiés ; séparer les données, les relations et la provenance. **Choix :** distinguer données de développement, réserve d'évaluation et éventuel entraînement, et conserver l'origine des éléments. Les associations synthétiques ne deviennent pas des affaires réelles. **Limite :** cohérence technique et réalisme juridique doivent être évalués séparément ; aucune validation générale ni autorisation d'entraînement ne découle de ces essais. Les artefacts Balladeur ne sont pas inclus dans cette sélection.

## Extraction, sélection et couverture

**Problème :** des passages de fichiers différents ont pu partager le même index local ; leur déduplication pouvait donc écarter un passage selon l'ordre des pièces. Les textes identiques dans plusieurs fichiers posent en outre une question de provenance. **Approche :** examiner l'identité d'un passage dans son document et conserver les occurrences ; distinguer les égalités de score, qui peuvent aussi rendre le résultat dépendant de l'ordre. Le correctif et ses consommateurs doivent être évalués sur leur version respective ; cette note ne déclare pas le dépôt public corrigé.

**Choix de mesure :** séparer ce qui existe dans le document, ce qui est extrait, sélectionné, envoyé au modèle et restitué. Une omission à la sélection ne doit pas être imputée à la génération. Conserver les doublons et leurs sources, et figer les attendus avant les essais lorsque possible. Les jeux exploratoires ne constituent pas une réserve indépendante.

## Résumés, contradictions et présentation : D5 à D7

**Problème :** le résumé peut omettre une version des faits, présenter une affirmation attribuée comme un fait établi, ajouter une relation causale ou altérer une date. Sur D6, deux conditions exploratoires ont montré des pertes de nature différente ; les deux textes étaient issus d'un seul appel par condition. **Limite :** cas construits et relecture par IA ; pas de conclusion de fiabilité générale ni de causalité établie.

Sur D7, les conditions `top2` et `top3` ont abouti aux mêmes contenus transmis dans l'essai étudié : elles n'ont donc pas exercé une véritable différence de troncature. Une consigne supplémentaire a rendu certaines attributions plus explicites dans une sortie, tout en présentant d'autres erreurs ou ambiguïtés. Elle n'établit pas une amélioration générale. Les textes des pièces, annotations, prompts et réponses historiques ne sont pas inclus ici.

**Choix de rendu :** clarifier qu'un état de traitement « complet » ne signifie pas que chaque phrase a été vérifiée. Un rendu de laboratoire a ajouté une mention de vérification non effectuée et retrouvé le rendu initial après retrait de cette ligne sur huit cas, avec la structure de rapport alors utilisée. La duplication de certains problèmes juridiques restait présente ; l'effet sur un avocat n'a pas été mesuré.

## Sources, navigation et lien sémantique

**Problème :** retrouver une page ou un passage ne démontre pas qu'il étaye une affirmation. Les expériences D7 ont étudié successivement les sources proposées pour des faits annotés, puis pour des portions d'un résumé enregistré. Des liens de démonstration vers trois pièces fictives ont été ouverts dans Safari ; un saut à la page 2 d'un PDF fictif séparé a été observé. Cela ne garantit ni le fonctionnement dans tous les navigateurs ni la fraîcheur des fichiers après génération.

**Choix :** présenter séparément source proposée, localisation vérifiée, lien sémantique à examiner et appréciation juridique. Les points de la démo s'appuyaient sur des records annotés manuellement, pas sur une compréhension automatique démontrée des PDF. Une grille de lecture humaine a été préparée ; une relecture IA ne se substitue pas à une lecture humaine indépendante.

## Règles et signalement

**Problème :** des règles simples sur les dates, la négation ou les mots peuvent produire des faux positifs, manquer des cas ou conclure à tort qu'un fait absent d'une liste est absent du dossier. **Approche :** versions successives de règles et de signalements sur données synthétiques ; conservation de l'incertitude et du caractère non exhaustif des annotations.

La brique [signalement v3](signalement_v3/) incluse cherche des mentions et produit des alertes ou ambiguïtés à examiner. Dans la revue historique, 22 cas de référence et deux cas enrichis ont été rejoués ; des limites demeuraient, notamment une ambiguïté sur des dates de granularité différente et un problème d'offset avec certains caractères Unicode. La présente publication ne prétend pas corriger ces limites. Absence d'alerte ne signifie ni absence d'erreur ni dossier exhaustif.

## Moteur local, performance et confidentialité

**Problème :** faire fonctionner des modèles localement tout en maîtrisant les ressources et les erreurs. **Approche expérimentale historique :** un adaptateur invoque `llama-completion` avec un contrat de génération et des contrôles de sortie. C'est `llama.cpp` qui fait le calcul ; ce n'est pas un moteur de calcul Beaume autonome. La grammaire et la validation technique ne démontrent pas la fidélité d'un résumé.

Des comparaisons de temps ont été explorées sur une machine et un modèle, avec des différences de cycle de vie et des métriques mémoire incomplètes ; elles ne démontrent aucune supériorité générale. Un cache de prompt a montré un gain sur des appels répétés selon les relevés historiques, mais il peut contenir des informations sensibles et ne valide pas la qualité du résultat. Les versions du cache ont évolué ; aucune version n'est incluse ni déclarée prête pour des données clients.

**Direction choisie :** explorer un moteur de calcul développé par le projet, avec CPU d'abord, puis matériel et cortex de coordination. Une brique pédagogique d'attention figure dans [calcul_reference](calcul_reference/) ; elle n'est ni un modèle complet ni une implémentation Rust ou GPU.

## Besoins et sécurité

Le premier terrain visé reste l'échange avec des avocats pour comprendre leur travail et évaluer l'utilité ; aucune validation professionnelle n'est revendiquée. Les scénarios de sécurité envisagent notamment des instructions hostiles dans des documents, les permissions, les fichiers malformés et la confidentialité. Une sélection partielle ou un détecteur d'instructions ne garantit pas la protection : ces essais restent à mener et à mesurer.
