"""Elo calculado en el backend desde el CSV (29/10/2026). Antes era una
foto fija del 24/08 (elo_ratings.json) que nunca se actualizo.
Correr desde backend/: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "services"))
import elo_ranking as E  # noqa: E402


def fila(fid, fecha, local, visitante, gl, gv, liga="Premier League", estado="FT"):
    return {"fixture_id": fid, "fecha": pd.Timestamp(fecha, tz="America/Bogota"), "estado": estado,
            "liga": liga, "equipo_local": local, "equipo_visitante": visitante,
            "goles_local": gl, "goles_visitante": gv}


class CalculoElo(unittest.TestCase):
    def test_un_partido_formula_del_backfill(self):
        # Iguales de arranque (misma liga): E_local = 1/(1+10^(-100/400)) = 0.6401
        df = pd.DataFrame([fila(1, "2026-01-01", "A", "B", 1, 0)])
        r, _ = E.calcular_elo(df)
        base = E.rating_inicial("Premier League")
        e_local = 1 / (1 + 10 ** (-100 / 400))
        self.assertAlmostEqual(r["A"]["rating"], round(base + 40 * (1 - e_local), 2))
        self.assertAlmostEqual(r["B"]["rating"], round(base - 40 * (1 - e_local), 2))
        self.assertEqual((r["A"]["n_partidos"], r["B"]["n_partidos"]), (1, 1))

    def test_liga_sin_tabla_arranca_en_1500(self):
        # Se mantiene a proposito (decision del usuario 29/10): cambiarlo es
        # un cambio de modelo aparte, con su propio backtest.
        self.assertEqual(E.rating_inicial("Liga Inventada"), 1500.0)

    def test_orden_cronologico_aunque_el_df_venga_al_reves(self):
        filas = [fila(1, "2026-01-01", "A", "B", 3, 0), fila(2, "2026-01-08", "B", "A", 2, 0)]
        r1, _ = E.calcular_elo(pd.DataFrame(filas))
        r2, _ = E.calcular_elo(pd.DataFrame(filas[::-1]))
        self.assertEqual(r1, r2)

    def test_no_terminados_sin_goles_y_selecciones_no_cuentan(self):
        df = pd.DataFrame([
            fila(1, "2026-01-01", "A", "B", 1, 0),
            fila(2, "2026-01-02", "A", "C", None, None, estado="NS"),
            fila(3, "2026-01-03", "A", "D", None, None),
            fila(4, "2026-01-04", "Argentina", "Brasil", 1, 0, liga="Mundial 2026"),
        ])
        r, _ = E.calcular_elo(df)
        self.assertEqual(set(r), {"A", "B"})
        self.assertEqual(r["A"]["n_partidos"], 1)

    def test_historico_un_registro_por_equipo_y_partido(self):
        df = pd.DataFrame([fila(1, "2026-01-01", "A", "B", 1, 1), fila(2, "2026-01-05", "A", "C", 0, 2)])
        _, h = E.calcular_elo(df, con_historico=True)
        self.assertEqual([x[0] for x in h], ["A", "B", "A", "C"])
        self.assertEqual(h[2][3], 2)  # A llega a 2 partidos


class CacheElo(unittest.TestCase):
    def setUp(self):
        E._cache_elo.update(clave=None, ratings={})

    def tearDown(self):
        E._cache_elo.update(clave=None, ratings={})

    def test_se_recalcula_cuando_cambia_el_csv(self):
        df1 = pd.DataFrame([fila(1, "2026-01-01", "A", "B", 1, 0)])
        E.asegurar_elo(df1, clave=("v1",))
        self.assertEqual(E.cargar_elo_ratings()["A"]["n_partidos"], 1)
        df2 = pd.concat([df1, pd.DataFrame([fila(2, "2026-01-08", "A", "Nuevo", 2, 2)])])
        E.asegurar_elo(df2, clave=("v2",))
        r = E.cargar_elo_ratings()
        self.assertEqual(r["A"]["n_partidos"], 2)
        self.assertIn("Nuevo", r)  # el equipo nuevo recibe rating

    def test_misma_clave_no_recalcula(self):
        df1 = pd.DataFrame([fila(1, "2026-01-01", "A", "B", 1, 0)])
        E.asegurar_elo(df1, clave=("v1",))
        E.asegurar_elo(pd.DataFrame([fila(2, "2026-01-08", "X", "Y", 1, 0)]), clave=("v1",))
        self.assertIn("A", E.cargar_elo_ratings())

    def test_sin_csv_cargado_no_hay_elo(self):
        self.assertEqual(E.cargar_elo_ratings(), {})


if __name__ == "__main__":
    unittest.main()
