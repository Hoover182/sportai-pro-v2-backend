"""Signo del handicap asiatico: "Local L" cubre si dif + L > 0 (dif = goles
local - goles visitante). Hasta el 2026-09-23 cada linea mostraba la de
signo opuesto.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import simulator as S

N = 8
XS, YS = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
DIF = XS - YS


def grid_con(marcadores):
    """Grilla con probabilidad repartida en {(goles_local, goles_visit): p}."""
    g = np.zeros((N, N))
    for (x, y), p in marcadores.items():
        g[x, y] = p
    return g


def formula_vieja(dif_grid, grid, linea):
    """La formula previa al arreglo (dif > linea), solo para comparar."""
    return (float(grid[dif_grid > linea].sum()), float(grid[dif_grid == linea].sum()),
            float(grid[dif_grid < linea].sum()))


class Signo(unittest.TestCase):
    def test_local_gana_2_a_0_seguro(self):
        g = grid_con({(2, 0): 1.0})
        casos = {
            -1.5: (1.0, 0.0, 0.0),   # Local -1.5: gana por 2 -> cubre
            -2.0: (0.0, 1.0, 0.0),   # Local -2: gana por exactamente 2 -> push
            -2.5: (0.0, 0.0, 1.0),   # Local -2.5: no llega -> no cubre
            0.5: (1.0, 0.0, 0.0),    # Local +0.5: gana -> cubre
            3.0: (1.0, 0.0, 0.0),
        }
        for linea, esperado in casos.items():
            with self.subTest(linea=linea):
                self.assertEqual(S.probabilidad_handicap_asiatico(DIF, g, linea), esperado)

    def test_visitante_gana_1_a_0_seguro(self):
        g = grid_con({(0, 1): 1.0})
        self.assertEqual(S.probabilidad_handicap_asiatico(DIF, g, 1.0), (0.0, 1.0, 0.0))    # Local +1 pierde por 1 -> push
        self.assertEqual(S.probabilidad_handicap_asiatico(DIF, g, 1.5), (1.0, 0.0, 0.0))    # Local +1.5 cubre
        self.assertEqual(S.probabilidad_handicap_asiatico(DIF, g, -0.5), (0.0, 0.0, 1.0))   # Local -0.5 no cubre

    def test_linea_cero_es_empate_devuelve(self):
        g = grid_con({(1, 0): 0.5, (1, 1): 0.3, (0, 2): 0.2})
        cubre, push, no_cubre = S.probabilidad_handicap_asiatico(DIF, g, 0.0)
        self.assertAlmostEqual(cubre, 0.5)
        self.assertAlmostEqual(push, 0.3)
        self.assertAlmostEqual(no_cubre, 0.2)

    def test_coincide_con_el_europeo_mismo_signo(self):
        rnd = np.random.default_rng(3)
        g = rnd.random((N, N))
        g /= g.sum()
        # europeo: prob_hcp_local_m1 = dif > 1 ("Local -1"), prob_hcp_local_p1 = dif > -1 ("Local +1")
        self.assertEqual(S.probabilidad_handicap_asiatico(DIF, g, -1.0),
                         (float(g[DIF > 1].sum()), float(g[DIF == 1].sum()), float(g[DIF < 1].sum())))
        self.assertEqual(S.probabilidad_handicap_asiatico(DIF, g, 1.0),
                         (float(g[DIF > -1].sum()), float(g[DIF == -1].sum()), float(g[DIF < -1].sum())))

    def test_mismas_probabilidades_solo_cambia_el_emparejamiento(self):
        rnd = np.random.default_rng(11)
        for _ in range(50):
            g = rnd.random((N, N))
            g /= g.sum()
            for linea in S.LINEAS_HANDICAP_ASIATICO:
                self.assertEqual(S.probabilidad_handicap_asiatico(DIF, g, linea), formula_vieja(DIF, g, -linea))

    def test_monotono_y_suma_1(self):
        rnd = np.random.default_rng(5)
        g = rnd.random((N, N))
        g /= g.sum()
        cubres = [S.probabilidad_handicap_asiatico(DIF, g, l)[0] for l in S.LINEAS_HANDICAP_ASIATICO]
        self.assertEqual(cubres, sorted(cubres))   # cuanto mas ventaja recibe el local, mas cubre
        for l in S.LINEAS_HANDICAP_ASIATICO:
            self.assertAlmostEqual(sum(S.probabilidad_handicap_asiatico(DIF, g, l)), 1.0)


class EnLaSimulacion(unittest.TestCase):
    def test_favorito_local_claro(self):
        sim = S.simular_partido_futbol(2.4, 0.6, 1.2, 0.8, 5.5, 3.5, 4.0)
        h = sim["handicap_asiatico"]
        # Local -2.5 (ganar por 3+) tiene que ser MENOS probable que Local +2.5 (no perder por 3+)
        self.assertLess(h[-2.5]["cubre"], h[2.5]["cubre"])
        self.assertAlmostEqual(h[-0.5]["cubre"], sim["prob_local"], places=9)       # Local -0.5 = gana local
        self.assertAlmostEqual(h[0.5]["cubre"], sim["prob_1x"], places=9)           # Local +0.5 = 1X
        self.assertEqual((h[-1.0]["cubre"], h[-1.0]["push"], h[-1.0]["no_cubre"]),
                         (sim["prob_hcp_local_m1"], sim["prob_hcp_empate_m1"], sim["prob_hcp_visit_m1"]))
        self.assertEqual((h[1.0]["cubre"], h[1.0]["push"], h[1.0]["no_cubre"]),
                         (sim["prob_hcp_local_p1"], sim["prob_hcp_empate_p1"], sim["prob_hcp_visit_p1"]))


if __name__ == "__main__":
    unittest.main()
