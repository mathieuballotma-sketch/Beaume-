from math import exp, sqrt

import pytest

from moteur_reference import attention_causale


def test_calcul_sur_deux_positions():
    resultat = attention_causale([[1., 0.], [0., 1.]],
                                  [[1., 0.], [0., 1.]],
                                  [[2., 0.], [0., 4.]])
    poids = exp(1 / sqrt(2)) / (1 + exp(1 / sqrt(2)))
    assert resultat[0] == pytest.approx([2., 0.])
    assert resultat[1] == pytest.approx([2 * (1 - poids), 4 * poids])


def test_position_future_ne_change_pas_le_passe():
    q, k, v = [[1.], [1.]], [[1.], [2.]], [[3.], [8.]]
    avant = attention_causale(q, k, v)
    apres = attention_causale(q + [[999.]], k + [[999.]], v + [[999.]])
    assert apres[:2] == avant


@pytest.mark.parametrize('q,k,v', [([], [], []), ([[1.]], [], [[1.]]),
                                    ([[1.]], [[1., 2.]], [[1.]]),
                                    ([[float('nan')]], [[1.]], [[1.]])])
def test_entrees_invalides_refusees(q, k, v):
    with pytest.raises(ValueError):
        attention_causale(q, k, v)
