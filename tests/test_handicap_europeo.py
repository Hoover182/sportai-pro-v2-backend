"""Handicap europeo +/-2 y +/-3 (3 desenlaces): m = "Local -k" (gana si
dif > k), p = "Local +k" (gana si dif > -k), empate = diferencia exacta.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import simulator as S

SUFIJOS = ["m1", "p1", "m2", "p2", "m3", "p3"]


def trio(sim, suf):
    return sim[f"prob_hcp_local_{suf}"], sim[f"prob_hcp_empate_{suf}"], sim[f"prob_hcp_visit_{suf}"]


def simular(media_a, media_b, **kw):
    return S.simular_partido_futbol(media_a, media_b, 1.2, 1.0, 5.0, 4.0, 4.0, **kw)


CASOS = [(2.4, 0.6), (1.4, 1.3), (0.7, 2.1), (3.2, 0.4)]


class HandicapEuropeo(unittest.TestCase):
    def test_trios_suman_1(self):
        for a, b in CASOS:
            sim = simular(a, b)
            for suf in SUFIJOS:
                with self.subTest(medias=(a, b), linea=suf):
                    self.assertAlmostEqual(sum(trio(sim, suf)), 1.0, places=9)

    def test_monotono(self):
        for a, b in CASOS:
            sim = simular(a, b)
            m = [sim[f"prob_hcp_local_m{k}"] for k in (1, 2, 3)]
            p = [sim[f"prob_hcp_local_p{k}"] for k in (1, 2, 3)]
            self.assertEqual(m, sorted(m, reverse=True))   # Local -1 >= -2 >= -3
            self.assertEqual(p, sorted(p))                 # Local +1 <= +2 <= +3
            self.assertLessEqual(m[0], p[0])

    def test_iguales_a_las_lineas_enteras_del_asiatico(self):
        # Mismos eventos, misma grid_handicap: backtest del asiatico los cubre
        for a, b in CASOS:
            sim = simular(a, b)
            h = sim["handicap_asiatico"]
            for k in (1, 2, 3):
                for suf, linea in ((f"m{k}", float(-k)), (f"p{k}", float(k))):
                    with self.subTest(medias=(a, b), linea=suf):
                        self.assertEqual(trio(sim, suf), (h[linea]["cubre"], h[linea]["push"], h[linea]["no_cubre"]))

    def test_con_elo_usa_la_grilla_reescalada(self):
        sim = simular(1.5, 1.2, elo_local=1700, elo_visitante=1450, peso_elo=0.5)
        sin_elo = simular(1.5, 1.2)
        h = sim["handicap_asiatico"]
        for k in (2, 3):
            for suf, linea in ((f"m{k}", float(-k)), (f"p{k}", float(k))):
                with self.subTest(linea=suf):
                    self.assertEqual(trio(sim, suf), (h[linea]["cubre"], h[linea]["push"], h[linea]["no_cubre"]))
                    self.assertNotEqual(trio(sim, suf), trio(sin_elo, suf))   # el Elo si movio la grilla
        self.assertAlmostEqual(sim["prob_hcp_local_p1"], sim["prob_1x"], places=9)   # Local +1 = 1X (post-Elo)

    def test_favorito_local_claro(self):
        sim = simular(3.2, 0.4)
        # ganar por 3+ es menos probable que por 2+, y "Local +3" casi seguro
        self.assertLess(sim["prob_hcp_local_m3"], sim["prob_hcp_local_m2"])
        self.assertGreater(sim["prob_hcp_local_p3"], 0.95)


if __name__ == "__main__":
    unittest.main()
