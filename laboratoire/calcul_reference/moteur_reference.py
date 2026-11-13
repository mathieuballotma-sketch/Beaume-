"""Brique pédagogique d'attention causale, sans moteur d'inférence externe.

Ce code accepte des vecteurs déjà calculés. Il ne charge pas de modèle réel,
ne contient pas de tokenizer et ne constitue pas une implémentation de Qwen.
"""
from math import exp, isfinite, sqrt


def attention_causale(requetes, cles, valeurs):
    """Calcule une tête d'attention ; chaque position ne voit pas le futur."""
    n = len(requetes)
    if n == 0 or len(cles) != n or len(valeurs) != n:
        raise ValueError('Les trois séquences doivent avoir la même longueur non nulle')
    d = len(requetes[0])
    dv = len(valeurs[0])
    if not d or not dv:
        raise ValueError('Les dimensions doivent être non nulles')
    if any(len(x) != d for x in requetes + cles) or any(len(x) != dv for x in valeurs):
        raise ValueError('Dimensions incohérentes')
    if any(not isfinite(x) for v in requetes + cles + valeurs for x in v):
        raise ValueError('Les entrées doivent être finies')
    resultat = []
    for i, requete in enumerate(requetes):
        scores = [sum(a * b for a, b in zip(requete, cles[j])) / sqrt(d)
                  for j in range(i + 1)]
        if any(not isfinite(s) for s in scores):
            raise ValueError('Débordement du calcul')
        maximum = max(scores)
        poids = [exp(s - maximum) for s in scores]
        total = sum(poids)
        resultat.append([sum((poids[j] / total) * valeurs[j][k]
                             for j in range(i + 1)) for k in range(dv)])
    return resultat
