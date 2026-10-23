"""Modelo de partido NBA (app/services/nba_model.py): ventana que cruza
temporadas, H2H de cada lado (bug del original), sin mirar el futuro,
semilla fija, back-to-back y localia. Datos inventados, sin red.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services import nba_model as M

A, B, C = 1, 2, 3


def _partidos(filas):
    """filas: (fecha, temporada, local, visitante, pts_local, pts_visitante)"""
    return pd.DataFrame([
        {"game_id": f"g{i:03d}", "fecha": f, "temporada": t, "tipo": "regular",
         "id_local": l, "id_visitante": v, "puntos_local": pl, "puntos_visitante": pv}
        for i, (f, t, l, v, pl, pv) in enumerate(filas)])


class Ventana(unittest.TestCase):
    def test_cruza_temporada_y_no_mira_el_futuro(self):
        filas = [(f"2026-04-{d:02d}", "2025-26", A, C, 100 + d, 90) for d in range(1, 10)]
        filas += [("2026-10-21", "2026-27", A, C, 130, 90),
                  ("2026-10-23", "2026-27", A, C, 200, 90)]   # el partido a predecir
        largo = M.partidos_por_equipo(_partidos(filas))
        u = M.ultimos_partidos(largo, A, "2026-10-23")
        self.assertEqual(len(u), 10)
        self.assertEqual(u.iloc[0]["fecha"], "2026-10-21")
        self.assertNotIn(200.0, set(u["pts"]))
        self.assertIn("2025-26", set(u["temporada"]))

    def test_puntos_permitidos_del_marcador_rival(self):
        largo = M.partidos_por_equipo(_partidos([
            ("2026-10-20", "2026-27", A, B, 110, 100),
            ("2026-10-21", "2026-27", B, A, 120, 104)]))
        s = M.estadisticas_equipo(largo, A, "2026-10-25")
        self.assertEqual(s["puntos"], 107)
        self.assertEqual(s["puntos_permitidos"], 110)
        self.assertEqual(s["std_puntos"], M.STD_MIN)   # std real 4.2 < minimo 5


class H2H(unittest.TestCase):
    def test_cada_lado_toma_sus_puntos(self):
        # En el cruce mas reciente B es local (en el original quedaba primero
        # y A se llevaba los 130 de B).
        largo = M.partidos_por_equipo(_partidos([
            ("2026-10-20", "2026-27", A, B, 100, 90),
            ("2026-10-22", "2026-27", B, A, 130, 80)]))
        h2h = M.enfrentamientos_directos(largo, A, B, "2026-10-25", "2026-27")
        self.assertEqual(sorted(h2h["pts"]), [80, 100])
        self.assertEqual(sorted(h2h["pts_rival"]), [90, 130])
        sa = {"puntos": 100, "puntos_permitidos": 100}
        sb = {"puntos": 100, "puntos_permitidos": 100}
        ma, mb = M.ajustar_medias_con_rival(sa, sb, h2h)
        self.assertAlmostEqual(ma, 100 * 0.8 + 90 * 0.2)    # A: (100+80)/2
        self.assertAlmostEqual(mb, 100 * 0.8 + 110 * 0.2)   # B: (90+130)/2

    def test_solo_misma_temporada(self):
        largo = M.partidos_por_equipo(_partidos([("2026-03-01", "2025-26", A, B, 100, 90)]))
        self.assertTrue(M.enfrentamientos_directos(largo, A, B, "2026-10-25", "2026-27").empty)


class Partido(unittest.TestCase):
    def setUp(self):
        filas = []
        for d in range(1, 21):
            filas.append((f"2026-03-{d:02d}", "2025-26", A, C, 115 + d % 5, 105))
            filas.append((f"2026-03-{d:02d}", "2025-26", B, C, 108 + d % 7, 110))
        self.largo = M.partidos_por_equipo(_partidos(filas))

    def test_semilla_fija_mismo_resultado(self):
        r1 = M.analizar_partido(self.largo, A, B, "2026-04-01", "2025-26")
        r2 = M.analizar_partido(self.largo, A, B, "2026-04-01", "2025-26")
        self.assertEqual(r1["prob_local"], r2["prob_local"])
        self.assertAlmostEqual(r1["prob_local"] + r1["prob_visitante"], 1.0)
        self.assertAlmostEqual(r1["total"], r1["proy_local"] + r1["proy_visitante"])
        self.assertAlmostEqual(sum(r1["cuartos"]["local"]), r1["proy_local"])

    def test_localia_sube_al_local(self):
        base = M.analizar_partido(self.largo, A, B, "2026-04-01", "2025-26")
        con = M.analizar_partido(self.largo, A, B, "2026-04-01", "2025-26",
                                 M.Params(ventaja_local=3.0))
        self.assertGreater(con["prob_local"], base["prob_local"])
        self.assertAlmostEqual(con["margen_local"] - base["margen_local"], 3.0, delta=0.05)

    def test_back_to_back(self):
        # A y B jugaron el 20/03: el 21/03 es back-to-back para los dos
        r = M.analizar_partido(self.largo, A, B, "2026-03-21", "2025-26",
                               M.Params(factor_fatiga=0.9))
        self.assertTrue(r["back_to_back_local"] and r["back_to_back_visitante"])
        sin = M.analizar_partido(self.largo, A, B, "2026-03-21", "2025-26")
        self.assertLess(r["total"], sin["total"] * 0.92)
        self.assertFalse(M.jugo_ayer(self.largo, A, "2026-04-01"))

    def test_sin_historial_devuelve_none(self):
        self.assertIsNone(M.analizar_partido(self.largo, A, 99, "2026-04-01", "2025-26"))


if __name__ == "__main__":
    unittest.main()
